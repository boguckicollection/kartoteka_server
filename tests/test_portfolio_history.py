"""Tests for portfolio history aggregation."""

import datetime as dt
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from kartoteka_web import models
from kartoteka_web.routes import cards


def _make_card(
    *,
    card_id: int,
    name: str,
    number: str,
    set_name: str,
    history_points: list[tuple[dt.datetime, float]],
) -> models.CollectionEntry:
    card = models.Card(id=card_id, name=name, number=number, set_name=set_name)
    price_history = [
        models.PriceHistory(card_id=card_id, price=price, recorded_at=timestamp)
        for timestamp, price in history_points
    ]
    card.price_history = price_history
    entry = models.CollectionEntry(user_id=1, card_id=card_id, quantity=1)
    entry.card = card
    return entry


def test_aggregate_portfolio_history_merges_daily_values():
    midnight = dt.datetime(2023, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    noon = dt.datetime(2023, 1, 1, 12, 0, tzinfo=dt.timezone.utc)

    entry_a = _make_card(
        card_id=1,
        name="Card A",
        number="A1",
        set_name="Set",
        history_points=[(midnight, 10.0)],
    )
    entry_b = _make_card(
        card_id=2,
        name="Card B",
        number="B1",
        set_name="Set",
        history_points=[(noon, 20.0)],
    )

    aggregated = cards._aggregate_portfolio_history([entry_a, entry_b])

    assert aggregated, "expected at least one aggregated point"
    assert len(aggregated) == 1
    timestamp, value = aggregated[0]
    assert timestamp.date() == midnight.date()
    assert value == 30.0
