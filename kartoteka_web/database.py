"""Database utilities for the Kartoteka web API."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager, contextmanager, nullcontext
from typing import AsyncIterator, Iterator
from weakref import WeakKeyDictionary

from sqlalchemy import inspect
from sqlalchemy.exc import NoSuchTableError
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("KARTOTEKA_DATABASE_URL", "sqlite:///./kartoteka.db")

USING_SQLITE = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if USING_SQLITE else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

DATABASE_WRITE_LOCK = threading.RLock() if USING_SQLITE else nullcontext()

_ASYNC_LOCKS: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]
_ASYNC_LOCKS = WeakKeyDictionary()
_ASYNC_LOCKS_GUARD = threading.Lock()


def _get_async_lock_for_current_loop() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    with _ASYNC_LOCKS_GUARD:
        lock = _ASYNC_LOCKS.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            _ASYNC_LOCKS[loop] = lock
    return lock


@asynccontextmanager
async def _async_database_write_lock() -> AsyncIterator[None]:
    if USING_SQLITE:
        lock = _get_async_lock_for_current_loop()
        async with lock:
            yield
    else:
        yield

logger = logging.getLogger(__name__)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    with DATABASE_WRITE_LOCK:
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
    _ensure_card_price_columns()
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables confirmed")


def _ensure_card_price_columns() -> None:
    """Add missing price columns on the card table for older schemas."""

    inspector = inspect(engine)

    try:
        existing_columns = {column["name"] for column in inspector.get_columns("card")}
    except NoSuchTableError:
        # Table does not exist yet, nothing to migrate.
        return

    missing_columns = [
        column_name
        for column_name in ("price", "price_7d_average")
        if column_name not in existing_columns
    ]

    if not missing_columns:
        return

    logger.info(
        "Migrating card table to include missing price columns: %s", missing_columns
    )

    with engine.begin() as connection:
        for column_name in missing_columns:
            connection.exec_driver_sql(
                f"ALTER TABLE card ADD COLUMN {column_name} REAL"  # noqa: S608
            )



async def get_session() -> AsyncIterator[Session]:
    """FastAPI dependency returning a new SQLModel session."""

    async with _async_database_write_lock():
        with Session(engine) as session:
            yield session
