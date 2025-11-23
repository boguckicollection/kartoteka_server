"""Card and collection management API routes backed by local data."""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import get_current_user, get_optional_user
from ..database import get_session, session_scope
from ..services import catalog_sync, tcg_api, crud
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
        icons_directory=set_utils.DEFAULT_ICON_DIRECTORY,
        url_base=set_utils.SET_ICON_URL_BASE,
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


def _card_record_to_search_schema(record: models.CardRecord) -> schemas.CardSearchResult:
    return schemas.CardSearchResult(
        name=record.name,
        number=record.number,
        number_display=record.number_display or record.number,
        total=record.total,
        set_name=record.set_name,
        set_code=record.set_code,
        rarity=record.rarity,
        image_small=record.image_small,
        image_large=record.image_large,
        set_icon=record.set_icon,
        set_icon_path=_local_set_icon_path(record.set_code, record.set_name),
        artist=record.artist,
        series=record.series,
        release_date=record.release_date,
        price=record.price,
        price_7d_average=record.price_7d_average,
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
    records: list[dict[str, Any]],
    detail: schemas.CardDetail,
    *,
    require_number_match: bool = False,
) -> dict[str, Any] | None:
    """Select the best matching card from remote search results.
    
    IMPORTANT: When set_code is provided, we require an EXACT match on both
    set_code AND number. This prevents returning the wrong card when searching
    for a specific card like "Charizard from Arceus set #1".
    """
    if not records:
        return None
    
    # Debug logging (set to DEBUG level to avoid production log clutter)
    logger.debug(f"_select_remote_card: Looking for set_code={detail.set_code}, number={detail.number}")
    logger.debug(f"_select_remote_card: Got {len(records)} records")
    for i, r in enumerate(records[:5]):
        logger.debug(f"  Record {i}: set_code={r.get('set_code')}, number={r.get('number')}, name={r.get('name')}")

    def _norm(value: Any) -> str:
        return (str(value or "").strip().lower())

    def _clean_number(value: Any) -> str:
        text_value = str(value or "").strip()
        if not text_value:
            return ""
        simplified = re.sub(r"[^0-9a-zA-Z]+", "", text_value)
        if not simplified:
            return ""
        normalized = text.sanitize_number(simplified)
        return normalized.lower()

    target_number_raw = detail.number or detail.number_display or ""
    target_number = _norm(target_number_raw)
    target_number_clean = _clean_number(target_number_raw)
    target_total_clean = _clean_number(detail.total)
    target_set_code = _norm(detail.set_code)
    target_set_code_clean = set_utils.clean_code(detail.set_code) or ""
    target_set_name = _norm(detail.set_name)

    # First pass: Try to find an EXACT match (set_code + number)
    # This is critical for /cards/info endpoint where user clicks specific card
    if target_set_code_clean and target_number_clean:
        for record in records:
            record_number_clean = _clean_number(record.get("number"))
            record_number_display_clean = _clean_number(record.get("number_display"))
            record_set_code_clean = set_utils.clean_code(record.get("set_code")) or ""
            
            # Check for exact set_code match
            set_matches = (
                record_set_code_clean == target_set_code_clean
                or _norm(record.get("set_code")) == target_set_code
            )
            
            # Check for exact number match
            number_matches = (
                record_number_clean == target_number_clean
                or record_number_display_clean == target_number_clean
            )
            
            if set_matches and number_matches:
                return record

    # Second pass: Scoring-based matching (fallback for less specific queries)
    best_score = -1
    best_record: dict[str, Any] | None = None

    for record in records:
        score = 0
        record_number_value = record.get("number")
        record_number_display = record.get("number_display")
        record_number_raw = record_number_value or record_number_display
        record_number = _norm(record_number_raw)
        record_number_clean = _clean_number(record_number_value)
        record_number_display_clean = _clean_number(record_number_display)
        combined_number_clean = record_number_clean or record_number_display_clean
        record_total_clean = _clean_number(record.get("total"))
        record_set_code = _norm(record.get("set_code"))
        record_set_code_clean = set_utils.clean_code(record.get("set_code")) or ""
        record_set_name = _norm(record.get("set_name"))

        # Number matching (higher priority)
        if target_number and record_number == target_number:
            score += 5
        if (
            target_number_clean
            and combined_number_clean
            and target_number_clean == combined_number_clean
        ):
            score += 4
        if (
            target_number_clean
            and combined_number_clean
            and combined_number_clean.startswith(target_number_clean)
        ):
            score += 1
            
        # Total matching
        if target_total_clean and record_total_clean:
            if target_total_clean == record_total_clean:
                score += 1
                
        # Set matching (INCREASED priority - set must match for correct card)
        if target_set_code and record_set_code == target_set_code:
            score += 10  # Increased from 3
        if (
            target_set_code_clean
            and record_set_code_clean
            and target_set_code_clean == record_set_code_clean
        ):
            score += 8  # Increased from 2
        if target_set_name and record_set_name == target_set_name:
            score += 5  # Increased from 1
            
        if score > best_score:
            best_score = score
            best_record = record

    if best_record and best_score > 0:
        if require_number_match and target_number_clean:
            best_number_clean = _clean_number(best_record.get("number"))
            best_number_display_clean = _clean_number(best_record.get("number_display"))
            combined_best_number = best_number_clean or best_number_display_clean
            if not combined_best_number or combined_best_number != target_number_clean:
                return None
        return best_record
    return None


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

    # FIXED: Nie zwracaj karty jeśli numer się nie zgadza
    # Poprzednio zwracało pierwszą kartę o danej nazwie, co powodowało duplikację
    # Teraz zwracamy None i tworzymy nową kartę
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


def _apply_card_price(card: models.Card, session: Session) -> bool:
    """Fetch and update price from CardRecord catalog if available."""
    from sqlmodel import select
    
    # Try to find price in CardRecord catalog
    name_norm = text.normalize(card.name, keep_spaces=True)
    set_name_norm = text.normalize(card.set_name, keep_spaces=True)
    
    # First try: exact match (name + set + number)
    stmt = select(models.CardRecord).where(
        models.CardRecord.name_normalized == name_norm,
        models.CardRecord.set_name_normalized == set_name_norm,
        models.CardRecord.number == card.number
    ).limit(1)
    
    card_record = session.exec(stmt).first()
    
    # Second try: if no exact match, try normalized number match
    if not card_record:
        number_clean = text.sanitize_number(card.number or "")
        if number_clean:
            stmt = select(models.CardRecord).where(
                models.CardRecord.name_normalized == name_norm,
                models.CardRecord.set_name_normalized == set_name_norm
            )
            candidates = session.exec(stmt).all()
            for candidate in candidates:
                candidate_number_clean = text.sanitize_number(candidate.number or "")
                if candidate_number_clean == number_clean:
                    card_record = candidate
                    break
    
    updated = False
    if card_record:
        # Update price if available
        if card_record.price is not None and card.price != card_record.price:
            card.price = card_record.price
            updated = True
        # Update 7-day average if available
        if card_record.price_7d_average is not None and card.price_7d_average != card_record.price_7d_average:
            card.price_7d_average = card_record.price_7d_average
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


def _apply_card_record_filters(
    stmt,
    *,
    name_norm: str,
    query_norm: str,
    number_clean: str,
    total_clean: str,
    set_name_norm: str,
    set_code_clean: str,
):
    if name_norm:
        stmt = stmt.where(models.CardRecord.name_normalized.contains(name_norm))
    elif query_norm:
        stmt = stmt.where(models.CardRecord.name_normalized.contains(query_norm))

    if number_clean:
        number_like = f"{number_clean}%"
        stmt = stmt.where(
            or_(
                models.CardRecord.number == number_clean,
                models.CardRecord.number.like(number_like),
                models.CardRecord.number_display == number_clean,
                models.CardRecord.number_display.like(number_like),
            )
        )

    if total_clean:
        stmt = stmt.where(models.CardRecord.total == total_clean)

    if set_code_clean:
        stmt = stmt.where(models.CardRecord.set_code_clean == set_code_clean)

    if set_name_norm:
        stmt = stmt.where(models.CardRecord.set_name_normalized.contains(set_name_norm))

    return stmt


@router.get("/search", response_model=schemas.CardSearchResponse)
def search_cards_endpoint(
    query: str | None = None,
    name: str | None = None,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    set_code: str | None = None,
    limit: int | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    per_page: int = 20,
    current_user: models.User | None = Depends(get_optional_user),
    session: Session = Depends(get_session),
):
    # Optional authentication - endpoint is accessible to all users
    # current_user will be None if not authenticated
    del current_user

    parsed_name = ""
    parsed_number: str | None = None
    parsed_total: str | None = None
    if query:
        parsed_name, parsed_number, parsed_total = _parse_card_query(query)

    set_name_value = (set_name or "").strip()
    set_code_value = (set_code or "").strip()
    total_value = total or parsed_total

    name_value = (name or parsed_name or "").strip()
    number_value = number or parsed_number
    result_cap = MAX_SEARCH_RESULTS
    if limit is not None and limit > 0:
        result_cap = max(1, min(limit, MAX_SEARCH_RESULTS))
    overall_cap = 100
    result_cap = min(result_cap, overall_cap)
    search_query = query or _compose_query(name_value, number_value, set_name_value)
    if not (search_query or name_value):
        return schemas.CardSearchResponse(items=[], total=0, page=1, per_page=20, total_count=0)
    if not name_value:
        name_value = search_query

    per_page_value = max(1, min(per_page or 1, 20))
    try:
        requested_page = int(page)
    except (TypeError, ValueError):
        requested_page = 1
    requested_page = max(1, requested_page)

    name_norm = text.normalize(name_value, keep_spaces=True)
    query_norm = text.normalize(search_query, keep_spaces=True)
    set_name_norm = text.normalize(set_name_value, keep_spaces=True)
    set_code_clean = set_utils.clean_code(set_code_value) or ""
    number_clean = (
        text.sanitize_number(str(number_value))
        if number_value is not None
        else ""
    )
    total_clean = (
        text.sanitize_number(str(total_value))
        if total_value is not None
        else ""
    )

    filtered_stmt = _apply_card_record_filters(
        select(models.CardRecord),
        name_norm=name_norm,
        query_norm=query_norm,
        number_clean=number_clean,
        total_clean=total_clean,
        set_name_norm=set_name_norm,
        set_code_clean=set_code_clean,
    )

    count_stmt = _apply_card_record_filters(
        select(func.count()).select_from(models.CardRecord),
        name_norm=name_norm,
        query_norm=query_norm,
        number_clean=number_clean,
        total_clean=total_clean,
        set_name_norm=set_name_norm,
        set_code_clean=set_code_clean,
    )
    total_local = session.exec(count_stmt).one()
    total_local = int(total_local or 0)

    # Only use local results if we have enough cards (at least per_page_value results)
    # Otherwise, fall through to remote API search for better coverage
    LOCAL_THRESHOLD = per_page_value
    if total_local >= LOCAL_THRESHOLD:
        capped_total = min(total_local, result_cap)
        total_pages = max(1, (capped_total + per_page_value - 1) // per_page_value)
        page_value = min(requested_page, total_pages)
        offset = (page_value - 1) * per_page_value
        limit_value = min(per_page_value, max(0, capped_total - offset))
        records: list[models.CardRecord] = []
        if limit_value > 0:
            records = session.exec(
                filtered_stmt
                .order_by(
                    models.CardRecord.name_normalized,
                    models.CardRecord.set_name_normalized,
                    models.CardRecord.number,
                    models.CardRecord.id,
                )
                .offset(offset)
                .limit(limit_value)
            ).all()

        items = [_card_record_to_search_schema(record) for record in records]
        total_remote_value = total_local if total_local > result_cap else None
        return schemas.CardSearchResponse(
            items=items,
            total=len(items),
            total_count=min(total_local, result_cap),
            total_remote=total_remote_value,
            page=page_value,
            per_page=per_page_value,
            suggested_query=None,
        )

    # Try search with query variants for flexible matching
    # e.g., "boss orders" -> "boss's order"
    search_name = name_value or search_query
    query_variants = text.expand_search_variants(search_name)
    
    records: list[dict[str, Any]] = []
    filtered_total = 0
    upstream_total = 0
    used_variant: str | None = None
    
    for variant in query_variants:
        records, filtered_total, upstream_total = tcg_api.search_cards(
            name=variant,
            number=number_value,
            set_name=set_name_value,
            set_code=set_code_value,
            total=total_value,
            limit=result_cap,
            sort=sort,
            order=order,
            page=1,
            per_page=per_page_value,
            rapidapi_key=RAPIDAPI_KEY,
            rapidapi_host=RAPIDAPI_HOST,
        )
        if records:
            used_variant = variant
            logger.debug(f"Search found results with variant: '{variant}' (original: '{search_name}')")
            break
    
    # If still no results, try original query as fallback
    if not records and query_variants and search_name not in query_variants:
        records, filtered_total, upstream_total = tcg_api.search_cards(
            name=search_name,
            number=number_value,
            set_name=set_name_value,
            set_code=set_code_value,
            total=total_value,
            limit=result_cap,
            sort=sort,
            order=order,
            page=1,
            per_page=per_page_value,
            rapidapi_key=RAPIDAPI_KEY,
            rapidapi_host=RAPIDAPI_HOST,
        )

    filtered_total_value = int(filtered_total or len(records))
    if len(records) > result_cap:
        records = records[:result_cap]

    suggestion = None
    if records and isinstance(records[0], dict):
        suggestion = records[0].get("name")

    changed_catalog = False
    for record in records:
        if isinstance(record, dict):
            _, created, updated = catalog_sync.upsert_card_record(session, record)
            if created or updated:
                changed_catalog = True

    if changed_catalog:
        session.commit()

    effective_total = min(result_cap, filtered_total_value)
    max_pages = max(1, (effective_total + per_page_value - 1) // per_page_value)
    page_value = min(requested_page, max_pages)

    start_index = (page_value - 1) * per_page_value
    end_index = start_index + per_page_value
    page_records = records[start_index:end_index]

    items = [
        _payload_to_search_schema(record)
        for record in page_records
        if isinstance(record, dict)
    ]
    return schemas.CardSearchResponse(
        items=items,
        total=filtered_total_value,  # Total number of results, not just items on this page
        total_count=effective_total,
        page=page_value,
        per_page=per_page_value,
        suggested_query=suggestion,
        total_remote=upstream_total or filtered_total_value,
    )


@router.get("/info", response_model=schemas.CardDetailResponse)
def card_info(
    name: str,
    number: str,
    total: str | None = None,
    set_code: str | None = None,
    set_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    range: str | None = None,
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
    range_value = (range or "").strip().lower() or None

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

    # First, try to find the card in the local CardRecord cache
    # This is faster and more reliable than the remote API text search
    local_card_record = None
    if set_code_value and number_value:
        # Try exact match on set_code + number
        stmt = select(models.CardRecord).where(
            models.CardRecord.set_code_clean == set_code_value.lower(),
            models.CardRecord.number == number_value,
        ).limit(1)
        local_card_record = session.exec(stmt).first()
        
        if not local_card_record:
            # Also try with case-insensitive set_code match
            number_clean = text.sanitize_number(number_value)
            all_candidates = session.exec(
                select(models.CardRecord).where(
                    models.CardRecord.name_normalized.contains(text.normalize(name_value, keep_spaces=True))
                )
            ).all()
            for candidate in all_candidates:
                candidate_set_code = set_utils.clean_code(candidate.set_code) or ""
                candidate_number = text.sanitize_number(candidate.number or "")
                if candidate_set_code == set_code_value.lower() and candidate_number == number_clean:
                    local_card_record = candidate
                    break
    
    if local_card_record:
        logger.debug(f"card_info: Found card in local cache: {local_card_record.name} - {local_card_record.set_code} - {local_card_record.number}")

    remote_results: list[dict[str, Any]] = []
    remote_fetch_limit = max(6, limit_value + 1)
    
    # If we found the card locally, convert it to the expected format
    if local_card_record:
        local_result = {
            "name": local_card_record.name,
            "number": local_card_record.number,
            "number_display": local_card_record.number_display or local_card_record.number,
            "total": local_card_record.total,
            "set_name": local_card_record.set_name,
            "set_code": local_card_record.set_code,
            "rarity": local_card_record.rarity,
            "image_small": local_card_record.image_small,
            "image_large": local_card_record.image_large,
            "artist": local_card_record.artist,
            "series": local_card_record.series,
            "release_date": local_card_record.release_date,
            "set_icon": local_card_record.set_icon,
            "set_icon_path": _local_set_icon_path(local_card_record.set_code, local_card_record.set_name),
            "price": local_card_record.price,
            "price_7d_average": local_card_record.price_7d_average,
            "id": local_card_record.remote_id,
        }
        remote_results = [local_result]
    
    # Only call remote API if we didn't find the card locally
    if not remote_results:
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
            if not remote_results and number_value:
                remote_results, _, _ = tcg_api.search_cards(
                    name=name,
                    number=None,
                    set_name=set_name,
                    set_code=set_code,
                    total=None,
                    limit=remote_fetch_limit,
                    per_page=remote_fetch_limit,
                    rapidapi_key=RAPIDAPI_KEY,
                    rapidapi_host=RAPIDAPI_HOST,
                )
            if not remote_results and (set_code_value or set_name_value):
                remote_results, _, _ = tcg_api.search_cards(
                    name=name,
                    number=None,
                    set_name=None,
                    set_code=None,
                    total=None,
                    limit=remote_fetch_limit,
                    per_page=remote_fetch_limit,
                    rapidapi_key=RAPIDAPI_KEY,
                    rapidapi_host=RAPIDAPI_HOST,
                )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to fetch remote card details for %s #%s: %s", name, number, exc)
            remote_results = []

    # Debug: Log search results before selection
    logger.info(f"card_info: Got {len(remote_results)} remote results for {name}, {number}, {set_code}")
    for i, r in enumerate(remote_results[:5]):
        logger.info(f"  Result {i}: set_code={r.get('set_code')}, number={r.get('number')}, name={r.get('name')}")
    logger.info(f"card_info: detail.set_code={detail.set_code}, detail.number={detail.number}")

    remote_card = (
        _select_remote_card(
            remote_results,
            detail,
            require_number_match=card is not None and bool(detail.number),
        )
        if remote_results
        else None
    )
    remote_card_id: str | None = None

    def _parse_date_param(value: str | None) -> dt.date | None:
        if not value:
            return None
        text_value = value.strip()
        if not text_value:
            return None
        try:
            return dt.date.fromisoformat(text_value)
        except ValueError:
            return None

    today = dt.date.today()
    requested_date_from = _parse_date_param(date_from)
    requested_date_to = _parse_date_param(date_to)
    date_to_value = requested_date_to or today
    if date_to_value > today:
        date_to_value = today
    if requested_date_from and requested_date_from <= date_to_value:
        date_from_value = requested_date_from
    elif range_value == "all":
        date_from_value = None
    else:
        date_from_value = date_to_value - dt.timedelta(days=30)

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
    if local_icon and not detail.set_icon_path:
        detail.set_icon_path = local_icon

    local_rarity_icon = tcg_api.resolve_rarity_icon_path(detail.rarity)
    if local_rarity_icon and local_rarity_icon != detail.rarity_symbol:
        detail.rarity_symbol = local_rarity_icon
    if not detail.rarity_symbol and detail.rarity_symbol_remote:
        detail.rarity_symbol = detail.rarity_symbol_remote

    detail.price_history = schemas.CardPriceHistory()
    logger.info(f"card_info: remote_card_id={remote_card_id}, fetching price history...")
    if remote_card_id:
        try:
            raw_history = tcg_api.fetch_card_price_history(
                remote_card_id,
                rapidapi_key=RAPIDAPI_KEY,
                rapidapi_host=RAPIDAPI_HOST,
                date_from=date_from_value,
                date_to=date_to_value,
            )
            logger.info(f"card_info: Got {len(raw_history)} raw history points")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to fetch price history for card %s: %s", remote_card_id, exc)
            raw_history = []

        normalized_history = tcg_api.normalize_price_history(raw_history)
        logger.info(f"card_info: Got {len(normalized_history)} normalized history points")

        if not normalized_history and date_from_value is not None:
            try:
                fallback_history = tcg_api.fetch_card_price_history(
                    remote_card_id,
                    rapidapi_key=RAPIDAPI_KEY,
                    rapidapi_host=RAPIDAPI_HOST,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Fallback price history fetch failed for card %s: %s",
                    remote_card_id,
                    exc,
                )
                fallback_history = []

            normalized_history = tcg_api.normalize_price_history(fallback_history)

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
        .options(
            selectinload(models.CollectionEntry.card),
            selectinload(models.CollectionEntry.product)
        )
    ).all()
    
    # Refresh prices for cards/products that don't have them
    for entry in entries:
        if entry.card and entry.card.price is None:
            _apply_card_price(entry.card, session)
        elif entry.product and entry.product.price is None:
            from .products import _apply_product_price
            _apply_product_price(entry.product, session)
    
    session.commit()
    return _serialize_entries(entries, session=session)


@router.post("/", response_model=schemas.CollectionEntryRead, status_code=status.HTTP_201_CREATED)
def add_card(
    payload: schemas.CollectionEntryCreate,
    background_tasks: BackgroundTasks,
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
        session.flush()
        _apply_card_price(card, session)
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
        if _apply_card_price(card, session):
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
    
    # Fetch price history in the background
    background_tasks.add_task(fetch_and_save_history_for_card, card.id)

    return _serialize_entry(entry, session=session)


def fetch_and_save_history_for_card(card_id: int):
    """
    Background task to fetch and save price history for a specific card.
    Uses its own session scope to be thread-safe.
    """
    logger.info(f"Background task started for card_id: {card_id}")
    with session_scope() as session:
        card = session.get(models.Card, card_id)
        if not card:
            logger.error(f"[BG Task] Card with id {card_id} not found.")
            return

        # Find the corresponding CardRecord to get the remote_id
        stmt = select(models.CardRecord).where(
            models.CardRecord.name == card.name,
            models.CardRecord.set_name == card.set_name,
            models.CardRecord.number == card.number
        ).limit(1)
        card_record = session.exec(stmt).first()

        if not (card_record and card_record.remote_id):
            logger.warning(f"[BG Task] No CardRecord or remote_id found for {card.name} ({card.set_name} #{card.number}). Cannot fetch history.")
            return

        logger.info(f"[BG Task] Found remote_id: {card_record.remote_id} for {card.name}. Fetching history...")
        try:
            today = dt.date.today()
            date_from = today - dt.timedelta(days=365)
            
            history_data = tcg_api.fetch_card_price_history(
                card_record.remote_id,
                date_from=date_from,
                date_to=today
            )
            
            if not history_data:
                logger.info(f"[BG Task] No price history returned from API for remote_id: {card_record.remote_id}.")
                return

            normalized_history = tcg_api.normalize_price_history(history_data)
            
            if normalized_history:
                added, updated = crud.upsert_price_history(
                    session, card_record_id=card_record.id, price_history=normalized_history
                )
                card_record.last_price_synced = dt.datetime.now(dt.timezone.utc)
                session.add(card_record)
                # The session is committed by the session_scope context manager
                logger.info(f"[BG Task] Success for {card.name}. Added: {added}, Updated: {updated} price points.")
            else:
                logger.info(f"[BG Task] API returned data, but it was empty after normalization for {card.name}.")

        except Exception as e:
            logger.error(f"[BG Task] Failed to fetch/save price history for {card.name}: {e}", exc_info=True)






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


def _fetch_collection_history(
    entries: list[models.CollectionEntry],
    days: int,
    session: Session,
) -> list[schemas.CollectionValueHistoryPoint]:
    """
    Fetch historical collection values, sourcing from local DB and backfilling from the API
    for any cards with missing or stale data.
    This implementation is optimized for performance and correctness.
    Now returns separate cards_value and products_value for each history point.
    """
    today = dt.date.today()
    date_from = today - dt.timedelta(days=days)

    # Separate cards and products
    card_entries = {entry.card.id: entry for entry in entries if entry.card and entry.quantity > 0}
    product_entries = [entry for entry in entries if entry.product and entry.quantity > 0]
    
    # Calculate total products value (products don't have historical prices, so it's constant)
    products_total = sum(
        (entry.product.price or 0.0) * (entry.quantity or 1) 
        for entry in product_entries
    )
    
    if not card_entries and not product_entries:
        return []
    
    # If no cards but we have products, return history with just products value
    if not card_entries:
        date_range = [date_from + dt.timedelta(days=x) for x in range((today - date_from).days + 1)]
        return [
            schemas.CollectionValueHistoryPoint(
                date=day.isoformat(), 
                value=round(products_total, 2),
                cards_value=0.0,
                products_value=round(products_total, 2)
            )
            for day in date_range
        ]

    card_map = {card_id: entry.card for card_id, entry in card_entries.items()}

    # Step 1: Get all relevant CardRecords for the cards in the collection
    card_identifiers = list(set((c.name, c.set_name, c.number) for c in card_map.values()))
    card_records_map: dict[tuple, models.CardRecord] = {}
    if card_identifiers:
        clauses = [
            (models.CardRecord.name == name and models.CardRecord.set_name == set_name and models.CardRecord.number == number)
            for name, set_name, number in card_identifiers
        ]
        card_records_stmt = select(models.CardRecord).where(or_(*clauses))
        card_records = session.exec(card_records_stmt).all()
        card_records_map = {(r.name, r.set_name, r.number): r for r in card_records}

    # Step 2: On-demand fetching for cards with missing/stale history
    stale_threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    records_to_fetch: list[models.CardRecord] = []
    
    for card in card_map.values():
        key = (card.name, card.set_name, card.number)
        record = card_records_map.get(key)
        if record and record.remote_id:
            last_synced = record.last_price_synced
            if last_synced and last_synced.tzinfo is None:
                last_synced = last_synced.replace(tzinfo=dt.timezone.utc)

            if not last_synced or last_synced < stale_threshold:
                records_to_fetch.append(record)

    if records_to_fetch:
        logger.info(f"Found {len(records_to_fetch)} cards with stale/missing price history. Fetching from API.")
        for i, record in enumerate(records_to_fetch):
            if i > 0:
                time.sleep(1.1)  # Rate limit
            try:
                logger.info(f"Fetching history for remote_id: {record.remote_id}")
                history_data = tcg_api.fetch_card_price_history(
                    record.remote_id, date_from=date_from, date_to=today,
                    rapidapi_key=RAPIDAPI_KEY, rapidapi_host=RAPIDAPI_HOST,
                )
                if history_data:
                    normalized_history = tcg_api.normalize_price_history(history_data)
                    if normalized_history:
                        added, updated = crud.upsert_price_history(
                            session, card_record_id=record.id, price_history=normalized_history
                        )
                        record.last_price_synced = dt.datetime.now(dt.timezone.utc)
                        session.add(record)
                        logger.info(f"Updated history for {record.name}: {added} added, {updated} updated.")
            except Exception as e:
                logger.error(f"Failed to fetch/save history for {record.name}: {e}", exc_info=True)
        session.commit()

    # Step 3: Create a mapping of Card.id -> CardRecord.id
    card_to_record_id_map: dict[int, int] = {
        card.id: card_records_map[key].id
        for card in card_map.values()
        if (key := (card.name, card.set_name, card.number)) in card_records_map
    }
    record_ids = list(card_to_record_id_map.values())
    if not record_ids:
        return []

    # Step 4: Fetch ALL relevant price history in one batch.
    # We fetch all history, not just from date_from, to establish a correct starting value.
    price_history_data = session.exec(
        select(models.PriceHistory)
        .where(models.PriceHistory.card_record_id.in_(record_ids))
        .order_by(models.PriceHistory.date)
    ).all()

    # Step 5: Pre-process history to find the initial price for each card at the beginning of the date range.
    latest_prices: dict[int, float] = {}
    for record_id in record_ids:
        # Fallback to the card's current price if no history is found.
        card_id = next((cid for cid, rid in card_to_record_id_map.items() if rid == record_id), None)
        if card_id and (card := card_map.get(card_id)):
            latest_prices[record_id] = card.price or 0.0

    for ph in price_history_data:
        if ph.card_record_id and ph.date < date_from:
            latest_prices[ph.card_record_id] = ph.price or 0.0
    
    # Group subsequent price points by date for efficient iteration
    from collections import defaultdict
    prices_by_date: dict[dt.date, dict[int, float]] = defaultdict(dict)
    for ph in price_history_data:
        if ph.card_record_id and ph.date >= date_from:
            prices_by_date[ph.date][ph.card_record_id] = ph.price or 0.0

    # Step 6: Iterate through the date range and calculate daily totals.
    value_history = []
    date_range = [date_from + dt.timedelta(days=x) for x in range((today - date_from).days + 1)]

    daily_cards_total = sum(
        (latest_prices.get(record_id, 0.0) * (card_entries[card_id].quantity or 1))
        for card_id, record_id in card_to_record_id_map.items()
    )

    for day in date_range:
        if day in prices_by_date:
            # Recalculate total value only when prices change
            for record_id, new_price in prices_by_date[day].items():
                card_id = next((cid for cid, rid in card_to_record_id_map.items() if rid == record_id), None)
                if card_id:
                    quantity = card_entries[card_id].quantity or 1
                    old_price = latest_prices.get(record_id, 0.0)
                    daily_cards_total -= old_price * quantity
                    daily_cards_total += new_price * quantity
                    latest_prices[record_id] = new_price

        # Total = cards + products (products value is constant)
        daily_total = daily_cards_total + products_total
        value_history.append(
            schemas.CollectionValueHistoryPoint(
                date=day.isoformat(), 
                value=round(daily_total, 2),
                cards_value=round(daily_cards_total, 2),
                products_value=round(products_total, 2)
            )
        )
        
    return value_history


@router.get("/stats", response_model=schemas.CollectionStats)
def get_collection_stats(
    use_history: bool = True,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get collection statistics including value history."""
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(
            selectinload(models.CollectionEntry.card),
            selectinload(models.CollectionEntry.product)
        )
    ).all()
    
    # Calculate current stats - separate cards and products
    total_cards = 0
    unique_cards = 0
    total_products = 0
    cards_value = 0.0
    products_value = 0.0
    purchase_value = 0.0
    purchase_cards_value = 0.0  # Sum of card values that have purchase price

    # Refresh prices for cards/products that don't have them
    for entry in entries:
        quantity = entry.quantity or 0
        purchase_price = entry.purchase_price or 0.0
        purchase_value += purchase_price * quantity
        
        if entry.card:
            total_cards += quantity
            unique_cards += 1
            if entry.card.price is None:
                _apply_card_price(entry.card, session)
            price = entry.card.price or 0.0
            cards_value += price * quantity
            # Track value of cards with purchase price set
            if entry.purchase_price is not None and entry.purchase_price > 0:
                purchase_cards_value += price * quantity
        elif entry.product:
            total_products += quantity
            from .products import _apply_product_price
            if entry.product.price is None:
                _apply_product_price(entry.product, session)
            price = entry.product.price or 0.0
            products_value += price * quantity
    
    session.commit()
    
    total_value = cards_value + products_value
    
    # Generate value history
    value_history: list[schemas.CollectionValueHistoryPoint] = []
    
    if use_history:
        # Fetch real historical data from the local database
        logger.info("Fetching historical prices for collection from local DB...")
        value_history = _fetch_collection_history(
            entries=list(entries),
            days=365,
            session=session,
        )
    
    return schemas.CollectionStats(
        total_cards=total_cards,
        unique_cards=unique_cards,
        total_products=total_products,
        total_value=total_value,
        cards_value=cards_value,
        products_value=products_value,
        purchase_value=purchase_value,
        purchase_cards_value=purchase_cards_value,
        value_history=value_history,
    )


@router.post("/refresh-prices", response_model=dict[str, Any])
def refresh_collection_prices(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Refresh prices for all cards and products in user's collection from cache."""
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(
            selectinload(models.CollectionEntry.card),
            selectinload(models.CollectionEntry.product)
        )
    ).all()
    
    updated_cards = 0
    updated_products = 0
    
    for entry in entries:
        if entry.card:
            if _apply_card_price(entry.card, session):
                session.add(entry.card)
                updated_cards += 1
        elif entry.product:
            # Import _apply_product_price from products module
            from .products import _apply_product_price
            if _apply_product_price(entry.product, session):
                session.add(entry.product)
                updated_products += 1
    
    total_updated = updated_cards + updated_products
    if total_updated > 0:
        session.commit()
    
    return {
        "message": f"Zaktualizowano ceny dla {updated_cards} kart i {updated_products} produktów",
        "updated_cards": updated_cards,
        "updated_products": updated_products,
        "total_updated": total_updated,
        "total_entries": len(entries)
    }


@router.get("/recently-added", response_model=list[schemas.CollectionEntryRead])
def get_recently_added_cards(
    limit: int = 10,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get recently added cards and products from user's collection."""
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(
            selectinload(models.CollectionEntry.card),
            selectinload(models.CollectionEntry.product)
        )
        .order_by(models.CollectionEntry.id.desc())
        .limit(limit)
    ).all()

    return entries


@router.get("/price-changes", response_model=list[dict[str, Any]])
def get_price_changes(
    limit: int = 10,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get cards with biggest price changes in user's collection."""
    entries = session.exec(
        select(models.CollectionEntry)
        .where(models.CollectionEntry.user_id == current_user.id)
        .options(
            selectinload(models.CollectionEntry.card),
            selectinload(models.CollectionEntry.product)
        )
    ).all()

    price_changes: list[dict[str, Any]] = []

    for entry in entries:
        if entry.card:
            current_price = entry.card.price or 0.0
            avg_price = entry.card.price_7d_average or 0.0

            # Only include cards with both prices
            if current_price > 0 and avg_price > 0:
                change = current_price - avg_price
                change_percent = (change / avg_price) * 100 if avg_price > 0 else 0.0

                price_changes.append({
                    "type": "card",
                    "id": entry.card.id,
                    "name": entry.card.name,
                    "number": entry.card.number,
                    "set_name": entry.card.set_name,
                    "set_code": entry.card.set_code,
                    "image_small": entry.card.image_small,
                    "current_price": current_price,
                    "average_price": avg_price,
                    "price_change": change,
                    "price_change_percent": round(change_percent, 2),
                })
        elif entry.product:
            current_price = entry.product.price or 0.0
            avg_price = entry.product.price_7d_average or 0.0

            # Only include products with both prices
            if current_price > 0 and avg_price > 0:
                change = current_price - avg_price
                change_percent = (change / avg_price) * 100 if avg_price > 0 else 0.0

                price_changes.append({
                    "type": "product",
                    "id": entry.product.id,
                    "name": entry.product.name,
                    "set_name": entry.product.set_name,
                    "set_code": entry.product.set_code,
                    "image_small": entry.product.image_small,
                    "current_price": current_price,
                    "average_price": avg_price,
                    "price_change": change,
                    "price_change_percent": round(change_percent, 2),
                })

    # Sort by absolute change percent (biggest changes first)
    price_changes.sort(key=lambda x: abs(x["price_change_percent"]), reverse=True)

    return price_changes[:limit]
