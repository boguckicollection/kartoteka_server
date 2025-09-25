"""Card and collection management API routes."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from collections import defaultdict
from typing import Any, Iterable, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_session
from ..utils import images as image_utils, sets as set_utils
from kartoteka import pricing
from rapidfuzz import fuzz

router = APIRouter(prefix="/cards", tags=["cards"])

SET_LOGO_DIR = Path("set_logos")

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
        number_clean = pricing.sanitize_number(clean_number)
        total_clean = pricing.sanitize_number(clean_total) if clean_total else ""
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


def _resolve_set_icon(set_code: str | None, set_name: str | None) -> str | None:
    code = set_utils.clean_code(set_code)
    if not code and set_name:
        code = set_utils.guess_set_code(set_name)
    if not code:
        return None
    candidate = SET_LOGO_DIR / f"{code}.png"
    if candidate.exists():
        return f"/set-logos/{candidate.name}"
    return None


def _enrich_card_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    info = set_utils.get_set_info(
        set_code=data.get("set_code"),
        set_name=data.get("set_name"),
    )
    if info:
        if info.get("era") and not data.get("series"):
            data["series"] = info.get("era")
        if info.get("total") and not data.get("total"):
            data["total"] = str(info.get("total"))
        if info.get("code") and not data.get("set_code"):
            data["set_code"] = info.get("code")
    local_icon = _resolve_set_icon(data.get("set_code"), data.get("set_name"))
    if not data.get("set_icon") and local_icon:
        data["set_icon"] = local_icon
    return data


def _prepare_card_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return image_utils.cache_card_images(_enrich_card_payload(payload))


def _normalise_search_value(value: str | None) -> str:
    return pricing.normalize(value or "") or (value or "").strip().lower()


def _sanitise_optional_number(value: str | None) -> str | None:
    cleaned = pricing.sanitize_number(str(value or ""))
    return cleaned or None


def _ensure_record_assets(session: Session, record: "models.CardRecord") -> bool:
    updated = False
    if record and not record.set_icon:
        icon = _resolve_set_icon(record.set_code, record.set_name)
        if icon:
            record.set_icon = icon
            updated = True
    if record and record.image_large and not record.image_small:
        record.image_small = record.image_large
        updated = True
    if updated:
        record.updated_at = dt.datetime.now(dt.timezone.utc)
        session.add(record)
    return updated


def _upsert_card_record(session: Session, payload: dict[str, Any]) -> "models.CardRecord" | None:
    data = _prepare_card_payload(payload)
    name_value = (data.get("name") or "").strip()
    number_value = pricing.sanitize_number(str(data.get("number") or ""))
    if not name_value or not number_value:
        return None

    set_name_value = (data.get("set_name") or "").strip()
    number_display = data.get("number_display") or data.get("number") or number_value
    total_value = _sanitise_optional_number(data.get("total"))
    set_code_value = data.get("set_code") or None
    set_code_clean = set_utils.clean_code(set_code_value)
    now = dt.datetime.now(dt.timezone.utc)
    set_icon_value = data.get("set_icon") or _resolve_set_icon(set_code_value, set_name_value)

    candidate = None
    if set_code_clean:
        candidate = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.number == number_value)
                & (models.CardRecord.set_code_clean == set_code_clean)
            )
        ).first()
    if candidate is None and set_name_value:
        candidate = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.number == number_value)
                & (models.CardRecord.set_name == set_name_value)
            )
        ).first()
    if candidate is None:
        candidate = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.name == name_value)
                & (models.CardRecord.number == number_value)
                & (models.CardRecord.set_name == set_name_value)
            )
        ).first()

    name_normalized = _normalise_search_value(name_value)
    set_name_normalized = (
        _normalise_search_value(set_name_value) if set_name_value else None
    )

    if candidate is None:
        record = models.CardRecord(
            name=name_value,
            name_normalized=name_normalized,
            number=number_value,
            number_display=number_display,
            total=total_value,
            set_name=set_name_value,
            set_name_normalized=set_name_normalized,
            set_code=set_code_value,
            set_code_clean=set_code_clean,
            rarity=data.get("rarity"),
            artist=data.get("artist"),
            series=data.get("series"),
            release_date=data.get("release_date"),
            image_small=data.get("image_small"),
            image_large=data.get("image_large"),
            set_icon=set_icon_value,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        return record

    updated = False

    def _apply(attr: str, value: Any, allow_none: bool = False) -> None:
        nonlocal updated
        if value is None and not allow_none:
            return
        if getattr(candidate, attr) != value:
            setattr(candidate, attr, value)
            updated = True

    _apply("name", name_value)
    _apply("name_normalized", name_normalized)
    _apply("number", number_value)
    _apply("number_display", number_display, allow_none=True)
    _apply("total", total_value, allow_none=True)
    _apply("set_name", set_name_value)
    _apply("set_name_normalized", set_name_normalized, allow_none=True)
    if set_code_value is not None:
        _apply("set_code", set_code_value, allow_none=True)
    if set_code_clean is not None:
        _apply("set_code_clean", set_code_clean, allow_none=True)
    if data.get("rarity"):
        _apply("rarity", data.get("rarity"), allow_none=True)
    if data.get("artist"):
        _apply("artist", data.get("artist"), allow_none=True)
    if data.get("series"):
        _apply("series", data.get("series"), allow_none=True)
    if data.get("release_date"):
        _apply("release_date", data.get("release_date"), allow_none=True)
    if data.get("image_small"):
        _apply("image_small", data.get("image_small"), allow_none=True)
    if data.get("image_large"):
        _apply("image_large", data.get("image_large"), allow_none=True)
    if set_icon_value:
        _apply("set_icon", set_icon_value, allow_none=True)

    if updated:
        candidate.updated_at = now
        session.add(candidate)
    return candidate


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
        "price_pln": record.price_pln,
        "last_price_update": record.price_updated_at,
    }


def _score_card_record(
    record: "models.CardRecord",
    *,
    query_text: str,
    number_clean: str | None = None,
    set_norm: str = "",
    total_clean: str | None = None,
) -> float:
    query_norm = pricing.normalize(query_text or "", keep_spaces=True)
    candidate_parts = [
        record.name or "",
        record.number_display or record.number or "",
        record.set_name or "",
    ]
    candidate_label = " ".join(part for part in candidate_parts if part).strip()
    candidate_norm = pricing.normalize(candidate_label, keep_spaces=True)
    name_norm = record.name_normalized or pricing.normalize(record.name or "")

    scores: list[float] = []
    if query_norm and candidate_norm:
        scores.append(float(fuzz.WRatio(query_norm, candidate_norm)))
        scores.append(float(fuzz.partial_ratio(query_norm, candidate_norm)))
    if query_norm and name_norm:
        scores.append(float(fuzz.partial_ratio(query_norm, name_norm)))
    if not scores and query_norm:
        scores.append(float(fuzz.partial_ratio(query_norm, pricing.normalize(record.name or ""))))

    base_score = max(scores) if scores else 0.0
    bonus = 0.0

    if number_clean:
        record_number = record.number or ""
        if record_number == number_clean:
            bonus += 30.0
        elif record_number.startswith(number_clean):
            bonus += 10.0

    if total_clean:
        record_total = pricing.sanitize_number(str(record.total or ""))
        if record_total == total_clean:
            bonus += 5.0

    if set_norm:
        record_set_norm = record.set_name_normalized or pricing.normalize(record.set_name or "")
        if record_set_norm == set_norm:
            bonus += 15.0
        elif record_set_norm and set_norm in record_set_norm:
            bonus += 5.0

    return base_score + bonus


def _search_catalogue(
    session: Session,
    *,
    query: str,
    name: str,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    limit: int = 50,
) -> list["models.CardRecord"]:
    search_term = name or query
    name_norm = _normalise_search_value(search_term)
    number_clean = _sanitise_optional_number(number)
    total_clean = _sanitise_optional_number(total)
    set_norm = _normalise_search_value(set_name) if set_name else ""
    query_norm = pricing.normalize(query or search_term or "", keep_spaces=True)

    stmt = select(models.CardRecord)
    name_filter_applied = False

    if name_norm:
        prefix = name_norm[:3] if len(name_norm) > 3 else name_norm
        if prefix:
            stmt = stmt.where(models.CardRecord.name_normalized.contains(prefix))
            name_filter_applied = True

    if number_clean:
        stmt = stmt.where(models.CardRecord.number == number_clean)
    if total_clean:
        stmt = stmt.where(models.CardRecord.total == total_clean)
    if set_norm:
        stmt = stmt.where(models.CardRecord.set_name_normalized.contains(set_norm))

    fetch_limit = max(1, min(max(limit * 4, 100), 500))
    stmt = stmt.limit(fetch_limit)
    records = session.exec(stmt).all()

    if not records and name_filter_applied:
        fallback_stmt = select(models.CardRecord)
        if number_clean:
            fallback_stmt = fallback_stmt.where(models.CardRecord.number == number_clean)
        if total_clean:
            fallback_stmt = fallback_stmt.where(models.CardRecord.total == total_clean)
        if set_norm:
            fallback_stmt = fallback_stmt.where(
                models.CardRecord.set_name_normalized.contains(set_norm)
            )
        records = session.exec(fallback_stmt.limit(fetch_limit)).all()

    scored = [
        (
            _score_card_record(
                record,
                query_text=query_norm or search_term,
                number_clean=number_clean,
                set_norm=set_norm,
                total_clean=total_clean,
            ),
            record,
        )
        for record in records
    ]
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].set_name or "",
            item[1].number or "",
            item[1].name or "",
        )
    )
    return [record for _score, record in scored[: max(1, limit)]]


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
    set_norm = pricing.normalize(set_name or "") if set_name else ""
    if set_norm:
        for record in records:
            if (record.set_name_normalized or "") == set_norm:
                return record
            if pricing.normalize(record.set_name or "") == set_norm:
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
    number_clean = pricing.sanitize_number(str(number or ""))
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
    stmt = select(models.CardRecord).where(models.CardRecord.id != base.id)
    if base.set_code_clean:
        stmt = stmt.where(models.CardRecord.set_code_clean == base.set_code_clean)
    elif base.set_name_normalized:
        stmt = stmt.where(models.CardRecord.set_name_normalized == base.set_name_normalized)
    else:
        return []
    stmt = stmt.order_by(models.CardRecord.number)
    stmt = stmt.limit(limit)
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


def _load_price_history(session: Session, card: models.Card | None) -> list[models.PriceHistory]:
    if not card or card.id is None:
        return []
    return session.exec(
        select(models.PriceHistory)
        .where(models.PriceHistory.card_id == card.id)
        .order_by(models.PriceHistory.recorded_at)
    ).all()


def _apply_variant_multiplier(price: float | None, entry: models.CollectionEntry) -> float | None:
    if price is None:
        return None
    multiplier = 1.0
    if entry.is_reverse or entry.is_holo:
        multiplier *= pricing.HOLO_REVERSE_MULTIPLIER
    try:
        return round(float(price) * multiplier, 2)
    except (TypeError, ValueError):
        return price


def _entry_price_points(
    entry: models.CollectionEntry,
    history: Sequence[models.PriceHistory] | None = None,
) -> list[tuple[dt.datetime, float]]:
    if history is None:
        history = []
    points: list[tuple[dt.datetime, float]] = []
    for record in history:
        price = _apply_variant_multiplier(record.price, entry)
        if price is None:
            continue
        points.append((record.recorded_at, float(price)))
    if entry.current_price is not None and entry.last_price_update:
        points.append((entry.last_price_update, float(entry.current_price)))
    points.sort(key=lambda item: item[0])
    return points


def _calculate_change(
    points: Sequence[tuple[dt.datetime, float]] | None,
) -> tuple[float, str]:
    if not points:
        return 0.0, "flat"
    latest_ts, latest_value = points[-1]
    baseline_value = latest_value
    threshold = latest_ts - dt.timedelta(hours=24)
    for ts, value in reversed(points[:-1]):
        if ts <= threshold:
            baseline_value = value
            break
    else:
        if len(points) >= 2:
            baseline_value = points[-2][1]
    change = round(latest_value - baseline_value, 2)
    epsilon = 0.01
    if change > epsilon:
        return change, "up"
    if change < -epsilon:
        return change, "down"
    return 0.0, "flat"


def _serialize_entry(
    entry: models.CollectionEntry,
    session: Session | None = None,
) -> schemas.CollectionEntryRead:
    schema = schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)
    history_records = None
    card = entry.card
    if card is not None:
        history_records = getattr(card, "price_history", None)
        if history_records is None and session is not None:
            history_records = _load_price_history(session, card)
    points = _entry_price_points(entry, history_records or [])
    change, direction = _calculate_change(points)
    schema.change_24h = round(change, 2) if points else 0.0
    schema.change_direction = direction
    return schema


def _aggregate_portfolio_history(
    entries: Sequence[models.CollectionEntry],
    session: Session | None = None,
) -> list[tuple[dt.datetime, float]]:
    combined: dict[dt.datetime, float] = defaultdict(float)
    for entry in entries:
        quantity = entry.quantity or 0
        if quantity <= 0:
            continue
        card = entry.card
        history_records = None
        if card is not None:
            history_records = getattr(card, "price_history", None)
            if history_records is None and session is not None:
                history_records = _load_price_history(session, card)
        for timestamp, price in _entry_price_points(entry, history_records or []):
            combined[timestamp] += price * quantity
    points = sorted((ts, round(value, 2)) for ts, value in combined.items())
    if not points:
        return []

    latest_timestamp = points[-1][0]
    if latest_timestamp.tzinfo is None:
        latest_reference = latest_timestamp.replace(tzinfo=dt.timezone.utc)
    else:
        latest_reference = latest_timestamp
    window_start = latest_reference - dt.timedelta(days=7)

    filtered: list[tuple[dt.datetime, float]] = []
    for timestamp, value in points:
        if timestamp.tzinfo is None:
            timestamp_ref = timestamp.replace(tzinfo=dt.timezone.utc)
        else:
            timestamp_ref = timestamp
        if timestamp_ref >= window_start:
            filtered.append((timestamp, value))

    if not filtered:
        filtered.append(points[-1])

    return filtered


def record_price_history(
    session: Session,
    card: models.Card | None,
    price: float | None,
    timestamp: dt.datetime | None = None,
) -> bool:
    """Persist ``price`` for ``card`` in the history table.

    Returns ``True`` when a new row was stored.
    """

    if price is None or card is None or card.id is None:
        return False
    try:
        value = round(float(price), 2)
    except (TypeError, ValueError):
        return False

    existing = session.exec(
        select(models.PriceHistory)
        .where(models.PriceHistory.card_id == card.id)
        .order_by(models.PriceHistory.recorded_at.desc())
    ).first()
    target_timestamp = timestamp or dt.datetime.now(dt.timezone.utc)
    if existing is not None:
        same_price = abs(existing.price - value) < 0.005

        def _normalize(ts: dt.datetime | None) -> dt.datetime | None:
            if ts is None:
                return None
            if ts.tzinfo is None:
                return ts.replace(tzinfo=dt.timezone.utc)
            return ts

        existing_ts = _normalize(existing.recorded_at)
        target_ts = _normalize(target_timestamp)
        same_moment = False
        if existing_ts and target_ts:
            same_moment = abs((existing_ts - target_ts).total_seconds()) < 60
        if same_price and same_moment:
            return False

    history = models.PriceHistory(
        card_id=card.id,
        price=value,
        recorded_at=target_timestamp,
    )
    session.add(history)
    return True


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


def _serialize_entries(
    entries: Iterable[models.CollectionEntry],
    session: Session | None = None,
) -> list[schemas.CollectionEntryRead]:
    return [_serialize_entry(entry, session=session) for entry in entries]


@router.get("/search", response_model=list[schemas.CardSearchResult])
def search_cards_endpoint(
    query: str | None = None,
    name: str | None = None,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    limit: int = 200,
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
    search_query = query or _compose_query(name_value, number_value, set_name)
    if not (search_query or name_value):
        return []
    if not name_value:
        name_value = search_query

    cleaned_limit = max(1, min(limit, 500))
    records = _search_catalogue(
        session,
        query=search_query,
        name=name_value,
        number=number_value,
        total=total_value,
        set_name=set_name,
        limit=cleaned_limit,
    )
    updated = False
    for record in records:
        updated = _ensure_record_assets(session, record) or updated

    if not records:
        api_results = pricing.search_cards(
            name=name_value,
            number=number_value,
            total=total_value,
            set_name=set_name,
            limit=cleaned_limit,
        )
        stored = False
        for payload in api_results:
            if _upsert_card_record(session, payload):
                stored = True
        if stored:
            session.commit()
            records = _search_catalogue(
                session,
                query=search_query,
                name=name_value,
                number=number_value,
                total=total_value,
                set_name=set_name,
                limit=cleaned_limit,
            )
            updated = False
            for record in records:
                updated = _ensure_record_assets(session, record) or updated
        else:
            records = []
    elif updated:
        session.commit()

    return [_record_to_search_schema(record) for record in records]


@router.get("/info", response_model=schemas.CardDetailResponse)
def card_info(
    name: str,
    number: str,
    total: str | None = None,
    set_code: str | None = None,
    set_name: str | None = None,
    related_limit: int = 6,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
): 
    del current_user

    number_clean = pricing.sanitize_number(str(number))
    total_clean = pricing.sanitize_number(str(total)) if total else None
    search_query = _compose_query(name, number, set_name)

    remote_results: list[dict[str, Any]] = []

    def _fetch_remote_results() -> list[dict[str, Any]]:
        nonlocal remote_results
        if not remote_results:
            remote_results = pricing.search_cards(
                name=name,
                number=number,
                total=total,
                set_name=set_name,
                limit=20,
            )
        return remote_results

    record = _locate_catalogue_record(
        session,
        name=name,
        number=number,
        set_code=set_code,
        set_name=set_name,
    )
    if record is None:
        records = _search_catalogue(
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
            if _upsert_card_record(session, payload):
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
                records = _search_catalogue(
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
            if _upsert_card_record(session, payload):
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
                records = _search_catalogue(
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

    history_rows = _load_price_history(session, card)
    history_needs_reload = False
    history = [
        schemas.PricePoint(price=row.price, recorded_at=row.recorded_at)
        for row in history_rows
    ]

    price_value: float | None = detail_data.get("price_pln")
    last_update = detail_data.get("last_price_update")
    if history_rows:
        price_value = history_rows[-1].price
        last_update = history_rows[-1].recorded_at

    if card and card.id is not None:
        entries = session.exec(
            select(models.CollectionEntry).where(
                models.CollectionEntry.card_id == card.id
            )
        ).all()
        for entry in entries:
            if entry.current_price is None:
                continue
            if entry.last_price_update and (
                not last_update or entry.last_price_update > last_update
            ):
                price_value = entry.current_price
                last_update = entry.last_price_update
            elif price_value is None:
                price_value = entry.current_price

    if price_value is None:
        fetched_price = pricing.fetch_card_price(
            name=detail_data.get("name") or name,
            number=number_value,
            set_name=resolved_set_name,
            set_code=resolved_set_code,
        )
        if fetched_price is not None:
            price_value = fetched_price
            last_update = dt.datetime.now(dt.timezone.utc)
            record.price_pln = float(fetched_price)
            record.price_updated_at = last_update
            record.updated_at = last_update
            session.add(record)
            should_commit = True
    else:
        if record.price_pln != price_value or record.price_updated_at != last_update:
            record.price_pln = price_value
            record.price_updated_at = last_update
            record.updated_at = dt.datetime.now(dt.timezone.utc)
            session.add(record)
            should_commit = True

    detail_data["price_pln"] = price_value
    detail_data["last_price_update"] = last_update

    if card and price_value is not None:
        timestamp_value = last_update if isinstance(last_update, dt.datetime) else None
        if timestamp_value is None:
            timestamp_value = dt.datetime.now(dt.timezone.utc)
            last_update = timestamp_value
            detail_data["last_price_update"] = timestamp_value
        if record_price_history(session, card, price_value, timestamp_value):
            history_needs_reload = True
            should_commit = True

    limit_value = max(0, min(related_limit, 24))
    related_items: list[schemas.CardSearchResult] = []
    if limit_value:
        related_records = _load_related_catalogue(session, record, limit_value + 1)
        if len(related_records) < limit_value:
            lookup_code = record.set_code_clean or set_utils.guess_set_code(resolved_set_name)
            stored_related = False
            if lookup_code:
                api_related = pricing.list_set_cards(lookup_code, limit=limit_value + 1)
                for item in api_related:
                    if _upsert_card_record(session, item):
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
            candidate_name = pricing.normalize(candidate.set_name or "")
            detail_name = pricing.normalize(record.set_name or "")
            if candidate_name and detail_name:
                return candidate_name == detail_name
            return False

        for item in related_records:
            if item.id == record.id or is_same_record(item):
                continue
            if _ensure_record_assets(session, item):
                should_commit = True
            related_items.append(_record_to_search_schema(item))
            if len(related_items) >= limit_value:
                break

    if should_commit:
        session.commit()

    if history_needs_reload and card:
        history_rows = _load_price_history(session, card)

    history = [
        schemas.PricePoint(price=row.price, recorded_at=row.recorded_at)
        for row in (history_rows or [])
    ]

    detail = schemas.CardDetail.model_validate(detail_data)
    return schemas.CardDetailResponse(
        card=detail,
        history=history,
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
        .options(
            selectinload(models.CollectionEntry.card).selectinload(
                models.Card.price_history
            )
        )
    ).all()
    return _serialize_entries(entries, session=session)


@router.get("/summary", response_model=schemas.PortfolioSummary)
def portfolio_summary(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(selectinload(models.CollectionEntry.card))
    ).all()
    total_quantity = sum(entry.quantity for entry in entries)
    estimated_value = sum((entry.current_price or 0) * entry.quantity for entry in entries)
    aggregated = _aggregate_portfolio_history(entries, session=session)
    change, direction = _calculate_change(aggregated)
    return schemas.PortfolioSummary(
        total_cards=len(entries),
        total_quantity=total_quantity,
        estimated_value=round(estimated_value, 2),
        change_24h=round(change, 2),
        direction=direction,
    )


@router.get("/portfolio/history", response_model=schemas.PortfolioHistoryResponse)
def portfolio_history_points(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(
            selectinload(models.CollectionEntry.card).selectinload(
                models.Card.price_history
            )
        )
    ).all()
    aggregated = _aggregate_portfolio_history(entries, session=session)
    points = [
        schemas.PortfolioHistoryPoint(timestamp=timestamp, value=value)
        for timestamp, value in aggregated
    ]
    change, direction = _calculate_change(aggregated)
    latest_value = points[-1].value if points else 0.0
    return schemas.PortfolioHistoryResponse(
        points=points,
        change_24h=round(change, 2) if points else 0.0,
        direction=direction,
        latest_value=round(latest_value, 2),
    )


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
    _upsert_card_record(session, catalog_payload)

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

    base_price = None
    price_timestamp: dt.datetime | None = None
    if catalog_record and catalog_record.price_pln is not None:
        base_price = catalog_record.price_pln
        price_timestamp = catalog_record.price_updated_at

    if base_price is None:
        base_price = pricing.fetch_card_price(
            name=card.name,
            number=card.number,
            set_name=card.set_name,
            set_code=card.set_code,
        )
        if base_price is not None and catalog_record:
            price_timestamp = dt.datetime.now(dt.timezone.utc)
            catalog_record.price_pln = float(base_price)
            catalog_record.price_updated_at = price_timestamp
            catalog_record.updated_at = price_timestamp
            session.add(catalog_record)

    entry.current_price = _apply_variant_multiplier(base_price, entry)
    timestamp = price_timestamp or dt.datetime.now(dt.timezone.utc)
    if entry.current_price is not None:
        entry.last_price_update = timestamp
    record_price_history(session, card, base_price, timestamp)

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


@router.post("/{entry_id}/refresh", response_model=schemas.CollectionEntryRead)
def refresh_entry_price(
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
        .options(selectinload(models.CollectionEntry.card))
    ).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    card = entry.card
    if card is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Entry has no card")

    catalog_payload = {
        "name": card.name,
        "number": card.number,
        "set_name": card.set_name,
        "set_code": card.set_code,
        "rarity": card.rarity,
        "image_small": card.image_small,
        "image_large": card.image_large,
    }
    _upsert_card_record(session, catalog_payload)

    catalog_record = _locate_catalogue_record(
        session,
        name=card.name,
        number=card.number,
        set_code=card.set_code,
        set_name=card.set_name,
    )

    base_price = pricing.fetch_card_price(
        name=card.name,
        number=card.number,
        set_name=card.set_name,
        set_code=card.set_code,
    )
    timestamp = dt.datetime.now(dt.timezone.utc)
    if base_price is not None and catalog_record:
        catalog_record.price_pln = float(base_price)
        catalog_record.price_updated_at = timestamp
        catalog_record.updated_at = timestamp
        session.add(catalog_record)

    entry.current_price = _apply_variant_multiplier(base_price, entry)
    entry.last_price_update = timestamp
    record_price_history(session, card, base_price, timestamp)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _serialize_entry(entry, session=session)
