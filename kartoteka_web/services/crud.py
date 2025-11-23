"""CRUD operations for the database."""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlmodel import Session, select

from .. import models


def upsert_price_history(
    session: Session,
    card_record_id: int,
    price_history: Sequence[dict[str, object]],
    *,
    timestamp: dt.datetime | None = None,
) -> tuple[int, int]:
    """
    Insert or update price history records for a card.
    
    Returns a tuple of (added, updated) counts.
    """
    now = timestamp or dt.datetime.now(dt.timezone.utc)
    added = 0
    updated = 0

    for entry in price_history:
        date_str = entry.get("date")
        price = entry.get("price")
        currency = entry.get("currency")

        if not all([date_str, price, currency]):
            continue

        try:
            date = dt.date.fromisoformat(str(date_str))
        except (ValueError, TypeError):
            continue

        stmt = select(models.PriceHistory).where(
            models.PriceHistory.card_record_id == card_record_id,
            models.PriceHistory.date == date,
        )
        record = session.exec(stmt).first()

        if record:
            # Update existing record if price or currency changed
            if record.price != price or record.currency != currency:
                record.price = price
                record.currency = str(currency)
                record.updated_at = now
                session.add(record)
                updated += 1
        else:
            # Create new record
            record = models.PriceHistory(
                card_record_id=card_record_id,
                date=date,
                price=price,
                currency=str(currency),
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            added += 1
            
    return added, updated
