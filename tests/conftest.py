"""Shared pytest fixtures for Kartoteka API tests."""

from __future__ import annotations

import importlib
import sys
import threading
from contextlib import suppress
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def app_environment(monkeypatch, tmp_path):
    """Configure an isolated application and database for each test."""

    db_path = tmp_path / "kartoteka.db"
    db_url = f"sqlite:///{db_path}"
    image_dir = tmp_path / "card-images"
    image_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("KARTOTEKA_DATABASE_URL", db_url)
    monkeypatch.setenv("CARD_IMAGE_DIR", str(image_dir))
    monkeypatch.setenv("KARTOTEKA_SECRET_KEY", "test-secret-key")

    from kartoteka_web import database

    with suppress(Exception):
        database.engine.dispose()

    engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
    database.engine = engine
    database.DATABASE_URL = db_url
    database.USING_SQLITE = True
    database.connect_args = {"check_same_thread": False}
    database.DATABASE_WRITE_LOCK = threading.RLock()
    if hasattr(database, "WeakKeyDictionary"):
        database._ASYNC_LOCKS = database.WeakKeyDictionary()  # type: ignore[attr-defined]
    database.init_db()

    importlib.invalidate_caches()
    server_module = sys.modules.get("server")
    if server_module is None:
        server_module = importlib.import_module("server")
    else:
        server_module = importlib.reload(server_module)

    monkeypatch.setattr(
        "kartoteka_web.utils.images.ensure_directory",
        lambda: image_dir,
    )
    monkeypatch.setattr(
        "kartoteka_web.utils.images.ensure_local_path",
        lambda value, **_: value,
    )

    password_hasher = lambda password: f"hashed:{password}"
    password_verifier = lambda plain, hashed: hashed == f"hashed:{plain}"
    monkeypatch.setattr("kartoteka_web.auth.get_password_hash", password_hasher)
    monkeypatch.setattr("kartoteka_web.auth.verify_password", password_verifier)
    monkeypatch.setattr("kartoteka_web.routes.users.get_password_hash", password_hasher)
    monkeypatch.setattr("kartoteka_web.routes.users.verify_password", password_verifier)

    return server_module


@pytest.fixture()
def api_client(app_environment):
    """Return a FastAPI test client bound to the isolated application."""

    with TestClient(app_environment.app) as client:
        yield client
