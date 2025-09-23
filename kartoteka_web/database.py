"""Database utilities for the Kartoteka web API."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("KARTOTEKA_DATABASE_URL", "sqlite:///./kartoteka.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


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

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency returning a new SQLModel session."""

    with Session(engine) as session:
        yield session
