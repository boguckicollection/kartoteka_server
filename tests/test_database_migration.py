"""Tests for database schema migrations."""

from __future__ import annotations

import importlib

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine


def _create_legacy_card_table(engine: Engine) -> None:
    """Create a legacy `card` table missing the price columns."""

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE card (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                number VARCHAR NOT NULL,
                set_name VARCHAR NOT NULL,
                set_code VARCHAR,
                rarity VARCHAR,
                image_small VARCHAR,
                image_large VARCHAR
            );
            """
        )


def test_init_db_adds_missing_price_columns(monkeypatch, tmp_path):
    """`init_db` should backfill price columns for legacy schemas."""

    db_path = tmp_path / "legacy.db"
    db_url = f"sqlite:///{db_path}"

    legacy_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _create_legacy_card_table(legacy_engine)
    legacy_engine.dispose()

    monkeypatch.setenv("KARTOTEKA_DATABASE_URL", db_url)

    import kartoteka_web.database as database

    # Reload the database module so it picks up the temporary database URL.
    database.engine.dispose()
    database = importlib.reload(database)

    database.init_db()

    inspector = inspect(database.engine)
    column_names = {column["name"] for column in inspector.get_columns("card")}
    assert {"price", "price_7d_average"}.issubset(column_names)

    # Insert and fetch a card with price data to prove the columns are operational.
    from kartoteka_web.models import Card  # Imported lazily to avoid circular imports.

    with Session(database.engine) as session:
        card = Card(
            name="Test Card",
            number="001",
            set_name="Test Set",
            price=9.99,
            price_7d_average=8.75,
        )
        session.add(card)
        session.commit()

        refreshed = session.get(Card, card.id)

    assert refreshed is not None
    assert refreshed.price == 9.99
    assert refreshed.price_7d_average == 8.75

