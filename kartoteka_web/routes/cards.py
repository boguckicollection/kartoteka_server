"""Card and collection management API routes."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_session
from ..utils import sets as set_utils
from kartoteka import pricing

router = APIRouter(prefix="/cards", tags=["cards"])

SET_LOGO_DIR = Path("set_logos")


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


def _select_best_result(
    results: list[dict[str, Any]],
    *,
    set_code: str | None = None,
    set_name: str | None = None,
) -> dict[str, Any] | None:
    code_clean = set_utils.clean_code(set_code)
    if code_clean:
        for item in results:
            if set_utils.clean_code(item.get("set_code")) == code_clean:
                return item
    name_norm = pricing.normalize(set_name or "") if set_name else ""
    if name_norm:
        for item in results:
            if pricing.normalize(item.get("set_name")) == name_norm:
                return item
    return results[0] if results else None


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


def record_price_history(
    session: Session,
    card: models.Card | None,
    price: float | None,
    timestamp: dt.datetime | None = None,
) -> None:
    """Persist ``price`` for ``card`` in the history table."""

    if price is None or card is None or card.id is None:
        return
    try:
        value = round(float(price), 2)
    except (TypeError, ValueError):
        return
    history = models.PriceHistory(
        card_id=card.id,
        price=value,
        recorded_at=timestamp or dt.datetime.now(dt.timezone.utc),
    )
    session.add(history)


def _serialize_entries(entries: Iterable[models.CollectionEntry]) -> list[schemas.CollectionEntryRead]:
    return [
        schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)
        for entry in entries
    ]


@router.get("/search", response_model=list[schemas.CardSearchResult])
def search_cards_endpoint(
    name: str,
    number: str | None = None,
    total: str | None = None,
    set_name: str | None = None,
    limit: int = 10,
    current_user: models.User = Depends(get_current_user),
):
    del current_user  # Only used to enforce authentication via dependency.
    cleaned_limit = max(1, min(limit, 25))
    results = pricing.search_cards(
        name=name,
        number=number,
        total=total,
        set_name=set_name,
        limit=cleaned_limit,
    )
    enriched = [_enrich_card_payload(result) for result in results]
    return [
        schemas.CardSearchResult.model_validate(result) for result in enriched
    ]


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
    search_results = pricing.search_cards(
        name=name,
        number=number,
        total=total,
        set_name=set_name,
        limit=20,
    )
    if not search_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono karty.")

    selected = _select_best_result(
        search_results,
        set_code=set_code,
        set_name=set_name,
    )
    if not selected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono karty.")

    detail_data = _enrich_card_payload(selected)
    if total and not detail_data.get("total"):
        total_value = pricing.sanitize_number(str(total))
        if total_value:
            detail_data["total"] = total_value
    if not detail_data.get("name"):
        detail_data["name"] = name

    number_value = detail_data.get("number") or pricing.sanitize_number(str(number))
    detail_data["number"] = number_value
    if not detail_data.get("number_display"):
        detail_data["number_display"] = number

    resolved_set_name = detail_data.get("set_name") or set_name or ""
    resolved_set_code = detail_data.get("set_code") or set_code or ""

    card = _find_card_record(
        session,
        name=detail_data.get("name") or name,
        number=number_value,
        set_name=resolved_set_name,
        set_code=set_utils.clean_code(resolved_set_code) or resolved_set_code,
    )

    history_rows = _load_price_history(session, card)
    history = [
        schemas.PricePoint(price=row.price, recorded_at=row.recorded_at)
        for row in history_rows
    ]

    price_value: float | None = history_rows[-1].price if history_rows else None
    last_update = history_rows[-1].recorded_at if history_rows else None

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
        price_value = pricing.fetch_card_price(
            name=detail_data.get("name") or name,
            number=number_value,
            set_name=resolved_set_name,
            set_code=resolved_set_code,
        )

    detail_data["price_pln"] = price_value
    detail_data["last_price_update"] = last_update

    limit_value = max(0, min(related_limit, 24))
    related_items: list[schemas.CardSearchResult] = []
    if limit_value:
        lookup_code = set_utils.clean_code(resolved_set_code)
        lookup_code = lookup_code or set_utils.clean_code(detail_data.get("set_code"))
        lookup_code = lookup_code or set_utils.guess_set_code(resolved_set_name)

        candidate_cards: list[dict[str, Any]] = []
        if lookup_code:
            candidate_cards = pricing.list_set_cards(lookup_code, limit=limit_value + 1)
        elif resolved_set_name:
            guessed = set_utils.guess_set_code(resolved_set_name)
            if guessed:
                candidate_cards = pricing.list_set_cards(guessed, limit=limit_value + 1)

        def is_same_card(candidate: dict[str, Any]) -> bool:
            same_number = (candidate.get("number") or "") == number_value
            if not same_number:
                return False
            candidate_code = set_utils.clean_code(candidate.get("set_code"))
            detail_code = set_utils.clean_code(detail_data.get("set_code"))
            if candidate_code and detail_code:
                return candidate_code == detail_code
            candidate_name = pricing.normalize(candidate.get("set_name"))
            detail_name = pricing.normalize(detail_data.get("set_name"))
            if candidate_name and detail_name:
                return candidate_name == detail_name
            return False

        for item in candidate_cards:
            if is_same_card(item):
                continue
            enriched = _enrich_card_payload(item)
            related_items.append(
                schemas.CardSearchResult.model_validate(enriched)
            )
            if len(related_items) >= limit_value:
                break

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
        .options(selectinload(models.CollectionEntry.card))
    ).all()
    return _serialize_entries(entries)


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
    return schemas.PortfolioSummary(
        total_cards=len(entries),
        total_quantity=total_quantity,
        estimated_value=round(estimated_value, 2),
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
        if updated:
            session.add(card)

    entry = models.CollectionEntry(
        owner=current_user,
        card=card,
        quantity=payload.quantity,
        purchase_price=payload.purchase_price,
        is_reverse=payload.is_reverse,
        is_holo=payload.is_holo,
    )

    base_price = pricing.fetch_card_price(
        name=card.name,
        number=card.number,
        set_name=card.set_name,
        set_code=card.set_code,
    )
    entry.current_price = _apply_variant_multiplier(base_price, entry)
    timestamp = dt.datetime.now(dt.timezone.utc)
    if entry.current_price is not None:
        entry.last_price_update = timestamp
    record_price_history(session, card, base_price, timestamp)

    session.add(entry)
    session.commit()
    session.refresh(entry)
    session.refresh(card)
    return schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)


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
    return schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)


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

    base_price = pricing.fetch_card_price(
        name=card.name,
        number=card.number,
        set_name=card.set_name,
        set_code=card.set_code,
    )
    entry.current_price = _apply_variant_multiplier(base_price, entry)
    timestamp = dt.datetime.now(dt.timezone.utc)
    entry.last_price_update = timestamp
    record_price_history(session, card, base_price, timestamp)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)
