"""Card and collection management API routes."""

from __future__ import annotations

import datetime as dt
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_session
from kartoteka import pricing

router = APIRouter(prefix="/cards", tags=["cards"])


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
    number: str,
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
    return [
        schemas.CardSearchResult.model_validate(result) for result in results
    ]


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
