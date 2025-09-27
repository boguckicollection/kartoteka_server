"""Tests ensuring remote search pagination retrieves enough records."""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def search_session(tmp_path, monkeypatch):
    db_path = tmp_path / "search.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("KARTOTEKA_DATABASE_URL", db_url)

    from kartoteka_web import database

    with suppress(Exception):
        database.engine.dispose()

    connect_args = {"check_same_thread": False}
    database.engine = create_engine(db_url, echo=False, connect_args=connect_args)
    SQLModel.metadata.create_all(database.engine)
    database.init_db()

    with Session(database.engine) as session:
        yield session


def _build_remote_payloads(total: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for index in range(total):
        results.append(
            {
                "name": f"Remote Card {index + 1}",
                "number": str(index + 1),
                "number_display": f"{index + 1}",
                "set_name": f"Set {index + 1:03d}",
                "set_code": f"RS{index + 1:03d}",
            }
        )
    return results


def test_remote_search_fetches_second_page(monkeypatch, search_session):
    from kartoteka_web.routes import cards
    from kartoteka_web import models

    remote_payloads = _build_remote_payloads(30)
    captured_limit: dict[str, int] = {}

    def fake_search_cards(*, limit: int, **_kwargs):
        captured_limit["value"] = limit
        return remote_payloads

    monkeypatch.setattr(cards.pricing, "search_cards", fake_search_cards)
    monkeypatch.setattr(cards, "_ensure_record_assets", lambda *a, **k: False)

    response = cards.search_cards_endpoint(
        query="Remote Card",
        page=2,
        page_size=20,
        current_user=object(),
        session=search_session,
    )

    assert captured_limit["value"] == 40
    assert response.total == len(remote_payloads)
    assert response.page == 2
    assert response.page_size == 20

    returned_names = {item.name for item in response.items}
    expected_names = {payload["name"] for payload in remote_payloads[20:]}
    assert returned_names == expected_names

    stored_records = search_session.exec(select(models.CardRecord)).all()
    assert len(stored_records) == len(remote_payloads)
