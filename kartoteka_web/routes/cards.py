"""Card and collection management API routes backed by local data."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import get_current_user, get_optional_user
from ..database import get_session
from ..services import tcg_api
from ..utils import images as image_utils, text, sets as set_utils

router = APIRouter(prefix="/cards", tags=["cards"])

MAX_SEARCH_RESULTS = 200

RAPIDAPI_KEY = (
    os.getenv("KARTOTEKA_RAPIDAPI_KEY")
    or os.getenv("POKEMONTCG_RAPIDAPI_KEY")
    or os.getenv("RAPIDAPI_KEY")
)
RAPIDAPI_HOST = (
    os.getenv("KARTOTEKA_RAPIDAPI_HOST")
    or os.getenv("POKEMONTCG_RAPIDAPI_HOST")
    or os.getenv("RAPIDAPI_HOST")
)

CARD_NUMBER_PATTERN = re.compile(
    r"(?i)([a-z]{0,5}\d+[a-z0-9]*)(?:\s*/\s*([a-z]{0,5}\d+[a-z0-9]*))?"
)

logger = logging.getLogger(__name__)

DEFAULT_SHOP_URL = "https://kartoteka.shop/pl/c/Karty-Pokemon/38"
SET_ICON_URL_BASE = "/icon/set"
SET_ICON_DIRECTORY = Path(__file__).resolve().parents[2] / "icon" / "set"


def _compose_query(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _prepare_query_text(value: str) -> str:
    def _spaces(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    text_value = re.sub(r"(?i)\bno\.?\s*", _spaces, value)
    text_value = text_value.replace("#", " ").replace("№", " ")
    return text_value


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
    text_value = (value or "").strip()
    if not text_value:
        return "", None, None

    search_text = _prepare_query_text(text_value)
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
        return text_value, None, None

    start, end, number_value, total_value = match_info
    name_candidate = f"{text_value[:start]} {text_value[end:]}".strip()
    if not name_candidate:
        name_candidate = text_value
    return name_candidate, number_value, total_value


def _normalize_lower(value: str | None) -> str:
    return (value or "").strip().lower()


def _local_set_icon_path(set_code: str | None, set_name: str | None = None) -> str | None:
    _, icon_path = set_utils.resolve_cached_set_icon(
        set_code=set_code,
        set_name=set_name,
        icons_directory=SET_ICON_DIRECTORY,
        url_base=SET_ICON_URL_BASE,
    )
    return icon_path


def _card_to_search_schema(card: models.Card) -> schemas.CardSearchResult:
    return schemas.CardSearchResult(
        name=card.name,
        number=card.number,
        number_display=card.number,
        total=None,
        set_name=card.set_name,
        set_code=card.set_code,
        rarity=card.rarity,
        image_small=card.image_small,
        image_large=card.image_large,
        set_icon=None,
        set_icon_path=_local_set_icon_path(card.set_code, card.set_name),
        artist=None,
        series=None,
        release_date=None,
        price=card.price,
        price_7d_average=card.price_7d_average,
    )


def _card_to_detail(card: models.Card) -> schemas.CardDetail:
    rarity_symbol = tcg_api.resolve_rarity_icon_path(card.rarity)
    return schemas.CardDetail(
        name=card.name,
        number=card.number,
        number_display=card.number,
        total=None,
        set_name=card.set_name,
        set_code=card.set_code,
        set_icon=None,
        set_icon_path=_local_set_icon_path(card.set_code, card.set_name),
        image_small=card.image_small,
        image_large=card.image_large,
        rarity=card.rarity,
        rarity_symbol=rarity_symbol,
        rarity_symbol_remote=None,
        artist=None,
        series=None,
        release_date=None,
        price=card.price,
        price_7d_average=card.price_7d_average,
        description=None,
        shop_url=DEFAULT_SHOP_URL,
        price_history=schemas.CardPriceHistory(),
    )


def _history_points_to_schema(
    points: list[dict[str, Any]]
) -> list[schemas.CardPriceHistoryPoint]:
    history: list[schemas.CardPriceHistoryPoint] = []
    for point in points:
        date_value = point.get("date")
        if not isinstance(date_value, str) or not date_value.strip():
            continue
        price_value = point.get("price")
        price_number: float | None
        if isinstance(price_value, (int, float)):
            price_number = float(price_value)
        elif isinstance(price_value, str):
            try:
                price_number = float(price_value.replace(",", "."))
            except ValueError:
                price_number = None
        else:
            price_number = None
        currency_value = point.get("currency")
        if isinstance(currency_value, str):
            currency_text = currency_value.strip() or None
        else:
            currency_text = None
        history.append(
            schemas.CardPriceHistoryPoint(
                date=date_value,
                price=price_number,
                currency=currency_text,
            )
        )
    return history


def _select_remote_card(
    records: list[dict[str, Any]], detail: schemas.CardDetail
) -> dict[str, Any] | None:
    if not records:
        return None

    def _norm(value: Any) -> str:
        return (str(value or "").strip().lower())

    target_number = _norm(detail.number)
    target_set_code = _norm(detail.set_code)
    target_set_name = _norm(detail.set_name)

    best_score = -1
    best_record: dict[str, Any] | None = None

    for record in records:
        score = 0
        record_number = _norm(record.get("number"))
        record_set_code = _norm(record.get("set_code"))
        record_set_name = _norm(record.get("set_name"))

        if target_number and record_number == target_number:
            score += 3
        if target_set_code and record_set_code == target_set_code:
            score += 3
        if target_set_name and record_set_name == target_set_name:
            score += 1
        if score > best_score:
            best_score = score
            best_record = record

    if best_record and best_score > 0:
        return best_record
    return records[0]


def _matches_filters(
    card: models.Card,
    *,
    name_filter: str,
    number_clean: str,
    set_filter: str,
    query_filter: str,
) -> bool:
    card_name_lower = (card.name or "").lower()
    card_set_lower = (card.set_name or "").lower()
    card_number_clean = text.sanitize_number(card.number or "")

    if number_clean:
        number_value = card.number or ""
        if card_number_clean != number_clean and not number_value.startswith(number_clean):
            return False
    if set_filter and set_filter not in card_set_lower:
        return False
    if name_filter:
        if name_filter not in card_name_lower:
            return False
    elif query_filter:
        combined = " ".join(
            part for part in (card.name, card.number, card.set_name) if part
        ).lower()
        if query_filter not in combined:
            return False
    return True


def _load_related_cards(
    session: Session,
    base: models.Card | None,
    limit: int,
) -> list[models.Card]:
    if not base or limit <= 0:
        return []
    stmt = (
        select(models.Card)
        .where(models.Card.id != base.id)
        .where(models.Card.name == base.name)
        .order_by(models.Card.set_name, models.Card.number, models.Card.id)
        .limit(limit)
    )
    return session.exec(stmt).all()


def _find_card(
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
    set_code_value = set_utils.clean_code(set_code) or ""

    if number_value:
        stmt = select(models.Card).where(models.Card.number == number_value)
        if set_name_value:
            stmt = stmt.where(models.Card.set_name == set_name_value)
        card = session.exec(stmt).first()
        if card:
            return card

    number_clean = text.sanitize_number(number_value)
    if number_clean and number_clean != number_value:
        stmt = select(models.Card).where(models.Card.number == number_clean)
        if set_name_value:
            stmt = stmt.where(models.Card.set_name == set_name_value)
        card = session.exec(stmt).first()
        if card:
            return card
        if name_value:
            candidates = session.exec(
                select(models.Card).where(models.Card.name == name_value)
            ).all()
            for candidate in candidates:
                candidate_clean = text.sanitize_number(candidate.number or "")
                if candidate_clean == number_clean:
                    return candidate

    if set_code_value:
        stmt = select(models.Card).where(models.Card.set_code.is_not(None))
        if set_name_value:
            stmt = stmt.where(models.Card.set_name == set_name_value)
        candidates = session.exec(stmt).all()
        for candidate in candidates:
            candidate_code = set_utils.clean_code(candidate.set_code)
            if candidate_code != set_code_value:
                continue
            numbers_to_match = {
                value for value in (number_value, number_clean) if value
            }
            if numbers_to_match:
                candidate_numbers = {
                    value
                    for value in (
                        candidate.number or "",
                        text.sanitize_number(candidate.number or ""),
                    )
                    if value
                }
                if candidate_numbers.isdisjoint(numbers_to_match):
                    continue
            return candidate

    if name_value and number_value:
        stmt = select(models.Card).where(
            (models.Card.name == name_value) & (models.Card.number == number_value)
        )
        card = session.exec(stmt).first()
        if card:
            return card

    if name_value:
        return session.exec(select(models.Card).where(models.Card.name == name_value)).first()

    return None


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


def _payload_to_search_schema(payload: dict[str, Any]) -> schemas.CardSearchResult:
    local_icon = payload.get("set_icon_path") or _local_set_icon_path(
        payload.get("set_code"), payload.get("set_name")
    )
    return schemas.CardSearchResult(
        name=payload.get("name") or "",
        number=payload.get("number") or "",
        number_display=payload.get("number_display"),
        total=payload.get("total"),
        set_name=payload.get("set_name") or "",
        set_code=payload.get("set_code"),
        rarity=payload.get("rarity"),
        image_small=payload.get("image_small"),
        image_large=payload.get("image_large"),
        set_icon=payload.get("set_icon"),
        set_icon_path=local_icon,
        artist=payload.get("artist"),
        series=payload.get("series"),
        release_date=payload.get("release_date"),
        price=payload.get("price"),
        price_7d_average=payload.get("price_7d_average"),
    )


@router.get("/search", response_model=schemas.CardSearchResponse)
def search_cards_endpoint(
    query: str | None = None,
    name: str | None = None,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    limit: int | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    per_page: int = 20,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    del current_user  # Only used to enforce authentication via dependency.

    parsed_name = ""
    parsed_number: str | None = None
    if query:
        parsed_name, parsed_number, _ = _parse_card_query(query)

    name_value = (name or parsed_name or "").strip()
    number_value = number or parsed_number
    result_cap = MAX_SEARCH_RESULTS
    if limit is not None and limit > 0:
        result_cap = max(1, min(limit, MAX_SEARCH_RESULTS))
    overall_cap = 100
    result_cap = min(result_cap, overall_cap)
    search_query = query or _compose_query(name_value, number_value, set_name)
    if not (search_query or name_value):
        return schemas.CardSearchResponse(items=[], total=0, page=1, per_page=20, total_count=0)
    if not name_value:
        name_value = search_query

    del session  # Database access unused when delegating to external API.

    per_page_value = max(1, min(per_page or 1, 20))
    try:
        requested_page = int(page)
    except (TypeError, ValueError):
        requested_page = 1
    requested_page = max(1, requested_page)

    records, filtered_total, upstream_total = tcg_api.search_cards(
        name=name_value or search_query,
        number=number_value,
        set_name=set_name,
        total=total,
        limit=overall_cap,
        sort=sort,
        order=order,
        page=1,
        per_page=per_page_value,
        rapidapi_key=RAPIDAPI_KEY,
        rapidapi_host=RAPIDAPI_HOST,
    )

    if result_cap < overall_cap:
        records = records[:result_cap]

    filtered_total = len(records)
    effective_total = min(overall_cap, filtered_total)
    max_pages = max(1, (effective_total + per_page_value - 1) // per_page_value)
    page_value = min(requested_page, max_pages)

    start_index = (page_value - 1) * per_page_value
    end_index = start_index + per_page_value
    page_records = records[start_index:end_index]

    items = [_payload_to_search_schema(record) for record in page_records]
    suggestion = records[0].get("name") if records else None
    return schemas.CardSearchResponse(
        items=items,
        total=len(page_records),
        total_count=effective_total,
        page=page_value,
        per_page=per_page_value,
        suggested_query=suggestion,
        total_remote=upstream_total,
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
    del current_user  # Kept for parity with authenticated view.

    limit_value = max(0, min(related_limit, 24))

    name_value = name.strip()
    number_value = number.strip()
    set_name_value = (set_name or "").strip()
    set_code_value = set_utils.clean_code(set_code) or None
    total_value = text.sanitize_number(total) if total else None

    card = _find_card(
        session,
        name=name,
        number=number,
        set_name=set_name,
        set_code=set_code,
    )

    if card is not None:
        detail = _card_to_detail(card)
        if total and not detail.total:
            detail.total = text.sanitize_number(total)
    else:
        detail = schemas.CardDetail(
            name=name_value or name,
            number=number_value or number,
            number_display=number_value or number,
            total=total_value,
            set_name=set_name_value,
            set_code=set_code_value,
            shop_url=DEFAULT_SHOP_URL,
        )

    detail.shop_url = (detail.shop_url or DEFAULT_SHOP_URL).strip() or DEFAULT_SHOP_URL

    remote_results: list[dict[str, Any]] = []
    remote_fetch_limit = max(6, limit_value + 1)
    try:
        remote_results, _, _ = tcg_api.search_cards(
            name=name,
            number=number,
            set_name=set_name,
            set_code=set_code,
            total=total,
            limit=remote_fetch_limit,
            per_page=remote_fetch_limit,
            rapidapi_key=RAPIDAPI_KEY,
            rapidapi_host=RAPIDAPI_HOST,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to fetch remote card details for %s #%s: %s", name, number, exc)
        remote_results = []

    remote_card = _select_remote_card(remote_results, detail) if remote_results else None
    remote_card_id: str | None = None

    if remote_card:
        remote_card_id_value = str(remote_card.get("id") or "").strip()
        remote_card_id = remote_card_id_value or None

        for attr in (
            "name",
            "number_display",
            "total",
            "set_name",
            "set_code",
            "set_icon_path",
            "image_small",
            "image_large",
            "rarity",
            "artist",
            "series",
            "release_date",
        ):
            value = remote_card.get(attr)
            if value:
                setattr(detail, attr, value)

        rarity_symbol_value = remote_card.get("rarity_symbol")
        if isinstance(rarity_symbol_value, str):
            rarity_symbol_clean = rarity_symbol_value.strip()
        else:
            rarity_symbol_clean = None
        if rarity_symbol_clean:
            detail.rarity_symbol = rarity_symbol_clean

        rarity_symbol_remote_value = remote_card.get("rarity_symbol_remote")
        if isinstance(rarity_symbol_remote_value, str):
            rarity_symbol_remote_clean = rarity_symbol_remote_value.strip()
        else:
            rarity_symbol_remote_clean = None
        if rarity_symbol_remote_clean:
            detail.rarity_symbol_remote = rarity_symbol_remote_clean

        price_value = remote_card.get("price")
        if price_value is not None:
            detail.price = price_value
        price_average = remote_card.get("price_7d_average")
        if price_average is not None:
            detail.price_7d_average = price_average

        set_icon_value = remote_card.get("set_icon")
        if set_icon_value:
            detail.set_icon = set_icon_value

        description_value = remote_card.get("description")
        if description_value:
            detail.description = description_value.strip()

        shop_url_value = remote_card.get("shop_url")
        if isinstance(shop_url_value, str) and shop_url_value.strip():
            detail.shop_url = shop_url_value.strip()

    detail.shop_url = detail.shop_url.strip() if detail.shop_url else DEFAULT_SHOP_URL
    if not detail.shop_url:
        detail.shop_url = DEFAULT_SHOP_URL

    local_icon = _local_set_icon_path(detail.set_code, detail.set_name)
    if local_icon:
        detail.set_icon_path = local_icon

    local_rarity_icon = tcg_api.resolve_rarity_icon_path(detail.rarity)
    if local_rarity_icon and local_rarity_icon != detail.rarity_symbol:
        detail.rarity_symbol = local_rarity_icon
    if not detail.rarity_symbol and detail.rarity_symbol_remote:
        detail.rarity_symbol = detail.rarity_symbol_remote

    detail.price_history = schemas.CardPriceHistory()
    if remote_card_id:
        try:
            raw_history = tcg_api.fetch_card_price_history(
                remote_card_id,
                rapidapi_key=RAPIDAPI_KEY,
                rapidapi_host=RAPIDAPI_HOST,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to fetch price history for card %s: %s", remote_card_id, exc)
            raw_history = []
        normalized_history = tcg_api.normalize_price_history(raw_history)
        if normalized_history:
            detail.price_history = schemas.CardPriceHistory(
                last_7=_history_points_to_schema(
                    tcg_api.slice_price_history(normalized_history, 7)
                ),
                last_30=_history_points_to_schema(
                    tcg_api.slice_price_history(normalized_history, 30)
                ),
                all=_history_points_to_schema(
                    tcg_api.slice_price_history(normalized_history)
                ),
            )

    if card is None and not remote_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono karty."
        )

    related_items: list[schemas.CardSearchResult] = []
    if card is not None:
        related_cards = _load_related_cards(session, card, limit_value)
        related_items = [
            _card_to_search_schema(item) for item in related_cards[:limit_value]
        ]
    elif remote_results:
        remote_related: list[dict[str, Any]] = []
        selected_id = remote_card.get("id") if remote_card else None
        for record in remote_results:
            if remote_card is not None and record is remote_card:
                continue
            if selected_id and record.get("id") == selected_id:
                continue
            remote_related.append(record)
        related_items = [
            _payload_to_search_schema(item) for item in remote_related[:limit_value]
        ]

    return schemas.CardDetailResponse(card=detail, related=related_items)


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

    if not name_value or not number_value or not set_name_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing card details")

    card = _find_card(
        session,
        name=name_value,
        number=number_value,
        set_name=set_name_value,
        set_code=set_code_value,
    )

    if card is None:
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
            session.commit()
            session.refresh(card)

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
