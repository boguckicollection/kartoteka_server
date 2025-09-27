"""Database utilities for the Kartoteka web API."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("KARTOTEKA_DATABASE_URL", "sqlite:///./kartoteka.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

logger = logging.getLogger(__name__)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def init_db() -> None:
    """Initialise database tables."""

    # Import models lazily to avoid circular imports during module initialisation.
    from . import models  # noqa: F401  # pylint: disable=unused-import

    logger.info("Ensuring database tables are created")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables confirmed")

    # Ensure the FTS index used for catalogue search exists and is synchronised
    # with the current dataset. ``exec_driver_sql`` is required so SQLite can
    # execute the ``CREATE VIRTUAL TABLE`` statement directly without SQLAlchemy
    # attempting to introspect it.
    logger.info("Synchronising full-text search index")
    with engine.connect() as connection:
        connection.exec_driver_sql(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS cardrecord_search
            USING fts5(
                card_id UNINDEXED,
                name_normalized,
                set_name_normalized
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO cardrecord_search (card_id, name_normalized, set_name_normalized)
            SELECT cardrecord.id, cardrecord.name_normalized, cardrecord.set_name_normalized
            FROM cardrecord
            WHERE cardrecord.id NOT IN (
                SELECT card_id FROM cardrecord_search
            )
            """
        )
    logger.info("Full-text search index synchronisation complete")


def get_session() -> Iterator[Session]:
    """FastAPI dependency returning a new SQLModel session."""

    with Session(engine) as session:
        yield session
