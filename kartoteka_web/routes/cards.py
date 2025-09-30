"""Card and collection management API routes."""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import database, models, schemas
from ..auth import get_current_user, get_optional_user
from ..database import get_session
from ..services import tcg_api
from ..utils import images as image_utils, sets as set_utils, text
from kartoteka_web import catalogue

try:  # pragma: no cover - optional dependency
    from rapidfuzz import fuzz
except ModuleNotFoundError:  # pragma: no cover - fallback for tests without rapidfuzz
    import difflib

    class _FuzzFallback:
        @staticmethod
        def WRatio(a: str, b: str) -> float:
            return difflib.SequenceMatcher(None, a or "", b or "").ratio() * 100

        @staticmethod
        def partial_ratio(a: str, b: str) -> float:
            return difflib.SequenceMatcher(None, a or "", b or "").ratio() * 100

    fuzz = _FuzzFallback()  # type: ignore[assignment]

router = APIRouter(prefix="/cards", tags=["cards"])

SCORE_THRESHOLD = text.SEARCH_SCORE_THRESHOLD
MAX_SEARCH_RESULTS = 200

CARD_NUMBER_PATTERN = re.compile(
    r"(?i)([a-z]{0,5}\d+[a-z0-9]*)(?:\s*/\s*([a-z]{0,5}\d+[a-z0-9]*))?"
)


def _compose_query(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _prepare_query_text(value: str) -> str:
    def _spaces(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    text = re.sub(r"(?i)\bno\.?\s*", _spaces, value)
    text = text.replace("#", " ").replace("№", " ")
    return text


def _is_probable_card_number(value: str) -> bool:
    if not value:
        return False
    digits = sum(char.isdigit() for char in value)
    letters = sum(char.isalpha() for char in value)
    if digits == 0:
        return False
    if "/" in value:
        return True
    if digits >= letters:
        return True
    return value[-1].isdigit()


def _parse_card_query(value: str | None) -> tuple[str, str | None, str | None]:
    text = (value or "").strip()
    if not text:
        return "", None, None

    search_text = _prepare_query_text(text)
    match_info: tuple[int, int, str, str | None] | None = None

    for match in CARD_NUMBER_PATTERN.finditer(search_text):
        raw_number = match.group(1) or ""
        raw_total = match.group(2) or ""
        clean_number = re.sub(r"[^0-9a-zA-Z]", "", raw_number)
        clean_total = re.sub(r"[^0-9a-zA-Z]", "", raw_total)
        if not clean_number or not _is_probable_card_number(clean_number):
            continue
        number_clean = text.sanitize_number(clean_number)
        total_clean = text.sanitize_number(clean_total) if clean_total else ""
        if not number_clean:
            continue
        start, end = match.span()
        match_info = (start, end, number_clean, total_clean or None)

    if match_info is None:
        return text, None, None

    start, end, number_value, total_value = match_info
    name_candidate = f"{text[:start]} {text[end:]}".strip()
    if not name_candidate:
        name_candidate = text
    return name_candidate, number_value, total_value


def _normalise_search_value(value: str | None) -> str:
    return text.normalize(value or "") or (value or "").strip().lower()


def _sanitise_optional_number(value: str | None) -> str | None:
    cleaned = text.sanitize_number(str(value or ""))
    return cleaned or None


def _ensure_record_assets(session: Session, record: "models.CardRecord") -> bool:
    return catalogue.ensure_record_assets(session, record)


def _record_to_search_schema(record: "models.CardRecord") -> schemas.CardSearchResult:
    payload = {
        "name": record.name,
        "number": record.number,
        "number_display": record.number_display or record.number,
        "total": record.total,
        "set_name": record.set_name,
        "set_code": record.set_code,
        "rarity": record.rarity,
        "image_small": record.image_small,
        "image_large": record.image_large,
        "set_icon": record.set_icon,
        "artist": record.artist,
        "series": record.series,
        "release_date": record.release_date,
    }
    return schemas.CardSearchResult.model_validate(payload)


def _record_to_detail_payload(record: "models.CardRecord") -> dict[str, Any]:
    return {
        "name": record.name,
        "number": record.number,
        "number_display": record.number_display,
        "total": record.total,
        "set_name": record.set_name,
        "set_code": record.set_code,
        "set_icon": record.set_icon,
        "image_small": record.image_small,
        "image_large": record.image_large,
        "rarity": record.rarity,
        "artist": record.artist,
        "series": record.series,
        "release_date": record.release_date,
    }


def _score_card_record(
    record: "models.CardRecord",
    *,
    query_text: str,
    number_clean: str | None = None,
    set_norm: str = "",
    total_clean: str | None = None,
) -> float:
    query_norm = text.normalize(query_text or "", keep_spaces=True)
    candidate_parts = [
        record.name or "",
        record.number_display or record.number or "",
        record.set_name or "",
    ]
    candidate_label = " ".join(part for part in candidate_parts if part).strip()
    candidate_norm = text.normalize(candidate_label, keep_spaces=True)
    name_norm = record.name_normalized or text.normalize(record.name or "")

    scores: list[float] = []
    if query_norm and candidate_norm:
        scores.append(float(fuzz.WRatio(query_norm, candidate_norm)))
        scores.append(float(fuzz.partial_ratio(query_norm, candidate_norm)))
    if query_norm and name_norm:
        scores.append(float(fuzz.partial_ratio(query_norm, name_norm)))
    if not scores and query_norm:
        scores.append(float(fuzz.partial_ratio(query_norm, text.normalize(record.name or ""))))

    base_score = max(scores) if scores else 0.0
    bonus = 0.0

    if number_clean:
        record_number = record.number or ""
        if record_number == number_clean:
            bonus += 30.0
        elif record_number.startswith(number_clean):
            bonus += 10.0

    if total_clean:
        record_total = text.sanitize_number(str(record.total or ""))
        if record_total == total_clean:
            bonus += 5.0

    if set_norm:
        record_set_norm = record.set_name_normalized or text.normalize(record.set_name or "")
        if record_set_norm == set_norm:
            bonus += 15.0
        elif record_set_norm and set_norm in record_set_norm:
            bonus += 5.0

    return base_score + bonus


def _build_fts_match_query(*values: str) -> str:
    tokens: list[str] = []
    for value in values:
        if not value:
            continue
        for token in re.findall(r"[0-9a-z]+", value):
            if token and token not in tokens:
                tokens.append(token)
    return " ".join(f"{token}*" for token in tokens)


def _fetch_cardrecord_candidate_ids(match_query: str, limit: int) -> list[int]:
    if not match_query or limit <= 0:
        return []
    with database.engine.connect() as connection:
        rows = connection.exec_driver_sql(
            """
            SELECT card_id
            FROM cardrecord_search
            WHERE cardrecord_search MATCH ?
            LIMIT ?
            """,
            (match_query, limit),
        )
        return [int(row[0]) for row in rows if row[0] is not None]


def _suggested_query_label(record: "models.CardRecord" | None) -> str | None:
    if not record:
        return None
    return record.name or record.number_display or record.number or None


def _search_catalogue(
    session: Session,
    *,
    query: str,
    name: str,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    limit: int | None = None,
) -> tuple[list["models.CardRecord"], int, "models.CardRecord" | None]:
    search_term = name or query
    name_norm = _normalise_search_value(search_term)
    number_clean = _sanitise_optional_number(number)
    total_clean = _sanitise_optional_number(total)
    set_norm = _normalise_search_value(set_name) if set_name else ""
    query_norm = text.normalize(query or search_term or "", keep_spaces=True)

    result_cap = MAX_SEARCH_RESULTS
    if limit is not None and limit > 0:
        result_cap = max(1, min(limit, MAX_SEARCH_RESULTS))

    base_filters: list[Any] = []
    if number_clean:
        base_filters.append(models.CardRecord.number == number_clean)
    if total_clean:
        base_filters.append(models.CardRecord.total == total_clean)
    if set_norm:
        base_filters.append(models.CardRecord.set_name_normalized.contains(set_norm))

    fetch_limit = max(result_cap * 4, result_cap, 100)
    fetch_limit = max(1, min(fetch_limit, 500))

    records: list[models.CardRecord] = []
    name_filter_applied = False
    count_filters: list[Any] = []

    if name_norm:
        match_query = _build_fts_match_query(name_norm, query_norm, set_norm)
        candidate_ids = _fetch_cardrecord_candidate_ids(match_query, fetch_limit)
        if candidate_ids:
            filters = [*base_filters, models.CardRecord.id.in_(candidate_ids)]
            ids_stmt = select(models.CardRecord)
            if filters:
                ids_stmt = ids_stmt.where(*filters)
            count_filters = filters
            records = session.exec(ids_stmt).all()

    if not records:
        filters = [*base_filters]
        if name_norm:
            prefix = name_norm[:3] if len(name_norm) > 3 else name_norm
            if prefix:
                filters.append(models.CardRecord.name_normalized.contains(prefix))
                name_filter_applied = True
        stmt = select(models.CardRecord)
        if filters:
            stmt = stmt.where(*filters)
        count_filters = filters
        records = session.exec(stmt.limit(fetch_limit)).all()

    if not records and name_filter_applied and name_norm:
        filters = [*base_filters, models.CardRecord.name_normalized.contains(name_norm)]
        fallback_stmt = select(models.CardRecord).where(*filters)
        count_filters = filters
        records = session.exec(fallback_stmt.limit(fetch_limit)).all()

    if not records:
        fallback_stmt = select(models.CardRecord)
        if base_filters:
            fallback_stmt = fallback_stmt.where(*base_filters)
        count_filters = base_filters
        records = session.exec(fallback_stmt.limit(fetch_limit)).all()

    if not count_filters:
        count_filters = base_filters

    count_stmt = select(func.count()).select_from(models.CardRecord)
    if count_filters:
        count_stmt = count_stmt.where(*count_filters)
    total_count = session.exec(count_stmt).one()
    if isinstance(total_count, tuple):
        total_count = total_count[0]
    total_count = int(total_count or 0)

    scored = []
    best_entry: tuple[float, models.CardRecord] | None = None
    for record in records:
        final_score = _score_card_record(
            record,
            query_text=query_norm or search_term,
            number_clean=number_clean,
            set_norm=set_norm,
            total_clean=total_clean,
        )
        if best_entry is None or final_score > best_entry[0]:
            best_entry = (final_score, record)
        scored.append((final_score, record))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].set_name or "",
            item[1].number or "",
            item[1].name or "",
        )
    )
    threshold = SCORE_THRESHOLD
    filtered = [entry for entry in scored if entry[0] >= threshold]
    filtered_total = len(filtered)
    visible = [record for _score, record in filtered[:result_cap]]
    if threshold and total_count:
        total_count = min(total_count, filtered_total)
    else:
        total_count = filtered_total
    total_count = min(total_count, result_cap)
    return visible, total_count, best_entry[1] if best_entry else None


def _select_best_record(
    records: list["models.CardRecord"],
    *,
    set_code: str | None = None,
    set_name: str | None = None,
) -> "models.CardRecord" | None:
    code_clean = set_utils.clean_code(set_code)
    if code_clean:
        for record in records:
            if record.set_code_clean == code_clean:
                return record
    set_norm = text.normalize(set_name or "") if set_name else ""
    if set_norm:
        for record in records:
            if (record.set_name_normalized or "") == set_norm:
                return record
            if text.normalize(record.set_name or "") == set_norm:
                return record
    return records[0] if records else None


def _locate_catalogue_record(
    session: Session,
    *,
    name: str,
    number: str,
    set_code: str | None = None,
    set_name: str | None = None,
) -> "models.CardRecord" | None:
    number_clean = text.sanitize_number(str(number or ""))
    if not number_clean:
        return None

    candidates: list[models.CardRecord] = []
    code_clean = set_utils.clean_code(set_code)
    if code_clean:
        candidates = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.number == number_clean)
                & (models.CardRecord.set_code_clean == code_clean)
            )
        ).all()
    if not candidates and set_name:
        set_norm = _normalise_search_value(set_name)
        candidates = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.number == number_clean)
                & (models.CardRecord.set_name_normalized == set_norm)
            )
        ).all()
    if not candidates:
        name_norm = _normalise_search_value(name)
        if name_norm:
            candidates = session.exec(
                select(models.CardRecord).where(
                    (models.CardRecord.number == number_clean)
                    & (models.CardRecord.name_normalized == name_norm)
                )
            ).all()
    if not candidates:
        candidates = session.exec(
            select(models.CardRecord).where(models.CardRecord.number == number_clean)
        ).all()
    return _select_best_record(candidates, set_code=set_code, set_name=set_name)


def _load_related_catalogue(
    session: Session,
    base: "models.CardRecord" | None,
    limit: int,
) -> list["models.CardRecord"]:
    if not base or limit <= 0:
        return []
    base_name_norm = base.name_normalized or text.normalize(base.name or "")
    if not base_name_norm:
        return []

    stmt = (
        select(models.CardRecord)
        .where(
            (models.CardRecord.id != base.id)
            & (models.CardRecord.name_normalized == base_name_norm)
        )
        .order_by(
            models.CardRecord.set_name,
            models.CardRecord.release_date,
            models.CardRecord.number,
        )
        .limit(limit)
    )
    return session.exec(stmt).all()

def _find_card_record(
    session: Session,
    *,
    name: str,
    number: str,
    set_name: str | None = None,
    set_code: str | None = None,
) -> models.Card | None:
    name_value = name.strip()
    number_value = number.strip()
    set_name_value = (set_name or "").strip()
    set_code_value = (set_code or "").strip()

    stmt = select(models.Card).where(
        (models.Card.name == name_value) & (models.Card.number == number_value)
    )
    if set_name_value:
        stmt = stmt.where(models.Card.set_name == set_name_value)
    card = session.exec(stmt).first()
    if card:
        return card

    if set_code_value:
        card = session.exec(
            select(models.Card).where(
                (models.Card.number == number_value)
                & (models.Card.set_code == set_code_value)
            )
        ).first()
        if card:
            return card

    return session.exec(
        select(models.Card).where(
            (models.Card.name == name_value) & (models.Card.number == number_value)
        )
    ).first()



def _apply_card_images(card: models.Card, card_data: schemas.CardBase) -> bool:
    """Update cached image paths for ``card`` based on ``card_data``."""

    small_path = image_utils.ensure_local_path(card_data.image_small, variant="small")
    large_path = image_utils.ensure_local_path(card_data.image_large, variant="large")

    current_small = card.image_small
    current_large = card.image_large

    small_value = small_path or current_small or card_data.image_small
    large_value = large_path or current_large or card_data.image_large

    if not small_value and large_value:
        small_value = large_value
    if not large_value and small_value:
        large_value = small_value

    updated = False
    if small_value and current_small != small_value:
        card.image_small = small_value
        updated = True
    if large_value and current_large != large_value:
        card.image_large = large_value
        updated = True
    return updated


def _serialize_entry(
    entry: models.CollectionEntry,
    session: Session | None = None,
) -> schemas.CollectionEntryRead:
    del session  # Session kept for compatibility; not used in lean metadata mode.
    return schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)


def _serialize_entries(
    entries: Iterable[models.CollectionEntry],
    session: Session | None = None,
) -> list[schemas.CollectionEntryRead]:
    return [_serialize_entry(entry, session=session) for entry in entries]


@router.get("/search", response_model=schemas.CardSearchResponse)
def search_cards_endpoint(
    query: str | None = None,
    name: str | None = None,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    limit: int | None = None,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    del current_user  # Only used to enforce authentication via dependency.

    parsed_name = ""
    parsed_number: str | None = None
    parsed_total: str | None = None
    if query:
        parsed_name, parsed_number, parsed_total = _parse_card_query(query)

    name_value = (name or parsed_name or "").strip()
    number_value = number or parsed_number
    total_value = total or parsed_total
    result_cap = MAX_SEARCH_RESULTS
    if limit is not None and limit > 0:
        result_cap = max(1, min(limit, MAX_SEARCH_RESULTS))
    search_query = query or _compose_query(name_value, number_value, set_name)
    if not (search_query or name_value):
        return schemas.CardSearchResponse(
            items=[],
            total=0,
        )
    if not name_value:
        name_value = search_query

    def _apply_assets(records: Sequence[models.CardRecord]) -> None:
        updated = False
        for record in records:
            updated = _ensure_record_assets(session, record) or updated
        if updated:
            session.commit()

    records, total_count, suggestion_record = _search_catalogue(
        session,
        query=search_query,
        name=name_value,
        number=number_value,
        total=total_value,
        set_name=set_name,
        limit=result_cap,
    )
    suggestion_name = _suggested_query_label(suggestion_record)
    _apply_assets(records)

    if not records:
        api_results = tcg_api.search_cards(
            name=name_value,
            number=number_value,
            total=total_value,
            set_name=set_name,
            limit=result_cap,
        )
        stored = False
        cached_records: list[models.CardRecord] = []
        for payload in api_results:
            record, changed = catalogue.upsert_card_record(session, payload)
            if record:
                cached_records.append(record)
                if _ensure_record_assets(session, record):
                    changed = True
            if changed:
                stored = True
        if stored:
            session.commit()
            records, total_count, suggestion_record = _search_catalogue(
                session,
                query=search_query,
                name=name_value,
                number=number_value,
                total=total_value,
                set_name=set_name,
                limit=result_cap,
            )
            suggestion_name = _suggested_query_label(suggestion_record)
            _apply_assets(records)
        elif cached_records:
            records = cached_records[:result_cap]
            total_count = min(len(cached_records), result_cap)
            suggestion_name = _suggested_query_label(cached_records[0])
            _apply_assets(records)
        else:
            records = []
            total_count = 0
            if not suggestion_name:
                suggestion_name = _suggested_query_label(suggestion_record)

    items = [_record_to_search_schema(record) for record in records]
    total_value = len(items)
    return schemas.CardSearchResponse(
        items=items,
        total=total_value,
        suggested_query=suggestion_name,
    )


@router.get("/info", response_model=schemas.CardDetailResponse)
def card_info(
    name: str,
    number: str,
    total: str | None = None,
    set_code: str | None = None,
    set_name: str | None = None,
    related_limit: int = 6,
    current_user: models.User | None = Depends(get_optional_user),
    session: Session = Depends(get_session),
):
    number_clean = text.sanitize_number(str(number))
    total_clean = text.sanitize_number(str(total)) if total else None
    search_query = _compose_query(name, number, set_name)

    remote_results: list[dict[str, Any]] = []

    def _fetch_remote_results() -> list[dict[str, Any]]:
        nonlocal remote_results
        if remote_results:
            return remote_results

        candidate_names: list[str | None] = [set_name]
        info = set_utils.get_set_info(set_code=set_code, set_name=set_name)
        if info:
            canonical = info.get("name")
            if canonical and canonical not in candidate_names:
                candidate_names.append(canonical)
        candidate_names.append(None)

        tried: set[str | None] = set()
        for candidate in candidate_names:
            if candidate in tried:
                continue
            tried.add(candidate)
            results = tcg_api.search_cards(
                name=name,
                number=number,
                total=total,
                set_name=candidate,
                limit=20,
            )
            if results:
                remote_results = results
                break
        else:
            remote_results = []

        return remote_results

    record = _locate_catalogue_record(
        session,
        name=name,
        number=number,
        set_code=set_code,
        set_name=set_name,
    )
    if record is None:
        records, _total, _suggestion = _search_catalogue(
            session,
            query=search_query,
            name=name,
            number=number,
            total=total,
            set_name=set_name,
            limit=20,
        )
        record = _select_best_record(records, set_code=set_code, set_name=set_name)

    if record is None:
        stored = False
        for payload in _fetch_remote_results():
            candidate, changed = catalogue.upsert_card_record(session, payload)
            if candidate:
                if _ensure_record_assets(session, candidate):
                    changed = True
            if changed:
                stored = True
        if stored:
            session.commit()
            record = _locate_catalogue_record(
                session,
                name=name,
                number=number,
                set_code=set_code,
                set_name=set_name,
            )
            if record is None:
                records, _total, _suggestion = _search_catalogue(
                    session,
                    query=search_query,
                    name=name,
                    number=number,
                    total=total,
                    set_name=set_name,
                    limit=20,
                )
                record = _select_best_record(records, set_code=set_code, set_name=set_name)

    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono karty.")

    needs_refresh = any(
        not getattr(record, field)
        for field in ("series", "artist", "image_large", "image_small", "rarity")
    )
    if needs_refresh:
        stored = False
        for payload in _fetch_remote_results():
            candidate, changed = catalogue.upsert_card_record(session, payload)
            if candidate:
                if _ensure_record_assets(session, candidate):
                    changed = True
            if changed:
                stored = True
        if stored:
            session.commit()
            record = _locate_catalogue_record(
                session,
                name=name,
                number=number,
                set_code=set_code,
                set_name=set_name,
            )
            if record is None:
                records, _total, _suggestion = _search_catalogue(
                    session,
                    query=search_query,
                    name=name,
                    number=number,
                    total=total,
                    set_name=set_name,
                    limit=20,
                )
                record = _select_best_record(records, set_code=set_code, set_name=set_name)
            if record is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono karty.")

    if _ensure_record_assets(session, record):
        session.commit()

    detail_data = _record_to_detail_payload(record)
    if not detail_data.get("name"):
        detail_data["name"] = name
    if total_clean and not detail_data.get("total"):
        detail_data["total"] = total_clean

    number_value = detail_data.get("number") or number_clean
    detail_data["number"] = number_value
    if not detail_data.get("number_display"):
        detail_data["number_display"] = number

    resolved_set_name = detail_data.get("set_name") or set_name or ""
    resolved_set_code = detail_data.get("set_code") or set_code or ""

    should_commit = False
    card = _find_card_record(
        session,
        name=detail_data.get("name") or name,
        number=number_value,
        set_name=resolved_set_name,
        set_code=set_utils.clean_code(resolved_set_code) or resolved_set_code,
    )

    if card is None and detail_data.get("name") and resolved_set_name:
        card = models.Card(
            name=detail_data.get("name") or name,
            number=number_value,
            set_name=resolved_set_name,
            set_code=set_utils.clean_code(resolved_set_code) or resolved_set_code or None,
            rarity=detail_data.get("rarity"),
        )
        card_data = schemas.CardBase(
            name=card.name,
            number=card.number,
            set_name=card.set_name,
            set_code=card.set_code,
            rarity=card.rarity,
            image_small=detail_data.get("image_small"),
            image_large=detail_data.get("image_large"),
        )
        _apply_card_images(card, card_data)
        session.add(card)
        session.flush()
        session.refresh(card)
        should_commit = True

    limit_value = max(0, min(related_limit, 24))
    related_items: list[schemas.CardSearchResult] = []
    if limit_value:
        related_records = _load_related_catalogue(session, record, limit_value + 1)
        base_name_norm = record.name_normalized or text.normalize(
            detail_data.get("name") or record.name or "",
        )
        if len(related_records) < limit_value and base_name_norm:
            stored_related = False
            seen_payloads: set[tuple[str, str, str]] = set()

            def _payload_key(payload: dict[str, Any]) -> tuple[str, str, str]:
                return (
                    text.normalize(payload.get("name") or ""),
                    text.sanitize_number(str(payload.get("number") or "")),
                    text.normalize(payload.get("set_name") or ""),
                )

            candidate_payloads: list[dict[str, Any]] = []
            for payload in _fetch_remote_results():
                if text.normalize(payload.get("name") or "") == base_name_norm:
                    candidate_payloads.append(payload)

            character_name = detail_data.get("name") or record.name or ""
            if character_name:
                search_results = tcg_api.search_cards(
                    name=character_name,
                    limit=limit_value + 5,
                )
                for payload in search_results:
                    if text.normalize(payload.get("name") or "") == base_name_norm:
                        candidate_payloads.append(payload)

            for payload in candidate_payloads:
                key = _payload_key(payload)
                if key in seen_payloads:
                    continue
                seen_payloads.add(key)
                candidate, changed = catalogue.upsert_card_record(session, payload)
                if candidate and _ensure_record_assets(session, candidate):
                    changed = True
                if changed:
                    stored_related = True

            if stored_related:
                session.commit()
                related_records = _load_related_catalogue(session, record, limit_value + 1)

        def is_same_record(candidate: models.CardRecord) -> bool:
            if candidate.number != number_value:
                return False
            candidate_code = candidate.set_code_clean
            detail_code = record.set_code_clean
            if candidate_code and detail_code:
                return candidate_code == detail_code
            candidate_name = text.normalize(candidate.set_name or "")
            detail_name = text.normalize(record.set_name or "")
            if candidate_name and detail_name:
                return candidate_name == detail_name
            return False

        for item in related_records:
            if is_same_record(item):
                continue
            if _ensure_record_assets(session, item):
                should_commit = True
            related_items.append(_record_to_search_schema(item))
            if len(related_items) >= limit_value:
                break

    if should_commit:
        session.commit()

    detail = schemas.CardDetail.model_validate(detail_data)
    return schemas.CardDetailResponse(
        card=detail,
        related=related_items,
    )


@router.get("/", response_model=list[schemas.CollectionEntryRead])
def list_collection(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(selectinload(models.CollectionEntry.card))
    ).all()
    return _serialize_entries(entries, session=session)


@router.post("/", response_model=schemas.CollectionEntryRead, status_code=status.HTTP_201_CREATED)
def add_card(
    payload: schemas.CollectionEntryCreate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    card_data = payload.card
    name_value = card_data.name.strip()
    number_value = (card_data.number or "").strip()
    set_name_value = card_data.set_name.strip()
    set_code_value = (card_data.set_code or "").strip() or None
    rarity_value = (card_data.rarity or "").strip() or None

    catalog_payload = card_data.model_dump(exclude_unset=True)
    catalog_payload.setdefault("name", name_value)
    catalog_payload.setdefault("number", number_value)
    catalog_payload.setdefault("set_name", set_name_value)
    catalog_payload.setdefault("set_code", set_code_value)
    catalog_payload.setdefault("rarity", rarity_value)
    catalog_record_candidate, _ = catalogue.upsert_card_record(session, catalog_payload)
    if catalog_record_candidate:
        _ensure_record_assets(session, catalog_record_candidate)

    catalog_record = _locate_catalogue_record(
        session,
        name=name_value,
        number=number_value,
        set_code=set_code_value,
        set_name=set_name_value,
    )

    card = session.exec(
        select(models.Card)
        .where(
            (models.Card.name == name_value)
            & (models.Card.number == number_value)
            & (models.Card.set_name == set_name_value)
        )
    ).first()
    if not card:
        card = models.Card(
            name=name_value,
            number=number_value,
            set_name=set_name_value,
            set_code=set_code_value,
            rarity=rarity_value,
        )
        _apply_card_images(card, card_data)
        session.add(card)
        session.commit()
        session.refresh(card)
    else:
        updated = False
        if set_code_value and card.set_code != set_code_value:
            card.set_code = set_code_value
            updated = True
        if rarity_value and not card.rarity:
            card.rarity = rarity_value
            updated = True
        if _apply_card_images(card, card_data):
            updated = True
        if updated:
            session.add(card)

    owner_id = current_user.id
    if owner_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if card.id is None:
        session.add(card)
        session.flush()

    entry = models.CollectionEntry(
        user_id=owner_id,
        card_id=card.id,
        quantity=payload.quantity,
        purchase_price=payload.purchase_price,
        is_reverse=payload.is_reverse,
        is_holo=payload.is_holo,
    )



    session.add(entry)
    session.commit()
    session.refresh(entry)
    session.refresh(card)
    return _serialize_entry(entry, session=session)


@router.patch("/{entry_id}", response_model=schemas.CollectionEntryRead)
def update_entry(
    entry_id: int,
    payload: schemas.CollectionEntryUpdate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    entry = session.exec(
        select(models.CollectionEntry)
        .where(
            (models.CollectionEntry.id == entry_id)
            & (models.CollectionEntry.user_id == current_user.id)
        )
        .options(selectinload(models.CollectionEntry.card))
    ).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    if payload.quantity is not None:
        entry.quantity = payload.quantity
    if payload.purchase_price is not None:
        entry.purchase_price = payload.purchase_price
    if payload.is_reverse is not None:
        entry.is_reverse = payload.is_reverse
    if payload.is_holo is not None:
        entry.is_holo = payload.is_holo

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _serialize_entry(entry, session=session)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    entry = session.exec(
        select(models.CollectionEntry)
        .where(
            (models.CollectionEntry.id == entry_id)
            & (models.CollectionEntry.user_id == current_user.id)
        )
    ).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    session.delete(entry)
    session.commit()
    return None


