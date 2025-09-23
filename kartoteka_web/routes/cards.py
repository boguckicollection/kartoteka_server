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
from kartoteka.pricing import HOLO_REVERSE_MULTIPLIER, fetch_card_price

router = APIRouter(prefix="/cards", tags=["cards"])


def _apply_variant_multiplier(price: float | None, entry: models.CollectionEntry) -> float | None:
    if price is None:
        return None
    multiplier = 1.0
    if entry.is_reverse or entry.is_holo:
        multiplier *= HOLO_REVERSE_MULTIPLIER
    try:
        return round(float(price) * multiplier, 2)
    except (TypeError, ValueError):
        return price


def _serialize_entries(entries: Iterable[models.CollectionEntry]) -> list[schemas.CollectionEntryRead]:
    return [
        schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)
        for entry in entries
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
    card = session.exec(
        select(models.Card)
        .where(
            (models.Card.name == card_data.name)
            & (models.Card.number == card_data.number)
            & (models.Card.set_name == card_data.set_name)
        )
    ).first()
    if not card:
        card = models.Card(
            name=card_data.name,
            number=card_data.number,
            set_name=card_data.set_name,
            set_code=card_data.set_code,
            rarity=card_data.rarity,
        )
        session.add(card)
        session.commit()
        session.refresh(card)

    entry = models.CollectionEntry(
        owner=current_user,
        card=card,
        quantity=payload.quantity,
        purchase_price=payload.purchase_price,
        is_reverse=payload.is_reverse,
        is_holo=payload.is_holo,
    )

    base_price = fetch_card_price(
        name=card.name,
        number=card.number,
        set_name=card.set_name,
        set_code=card.set_code,
    )
    entry.current_price = _apply_variant_multiplier(base_price, entry)
    if entry.current_price is not None:
        entry.last_price_update = dt.datetime.now(dt.timezone.utc)

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

    base_price = fetch_card_price(
        name=card.name,
        number=card.number,
        set_name=card.set_name,
        set_code=card.set_code,
    )
    entry.current_price = _apply_variant_multiplier(base_price, entry)
    entry.last_price_update = dt.datetime.now(dt.timezone.utc)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return schemas.CollectionEntryRead.model_validate(entry, from_attributes=True)
