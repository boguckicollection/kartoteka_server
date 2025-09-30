import sys
from contextlib import suppress
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine


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


def _seed_charizard(session: Session) -> None:
    from kartoteka_web import catalogue

    payload = {
        "name": "Charizard",
        "number": "4",
        "set_name": "Base Set",
    }
    record, created = catalogue.upsert_card_record(session, payload)
    if record is not None and created:
        session.add(record)
    session.commit()


def test_card_search_suggests_and_filters(monkeypatch, search_session):
    from kartoteka_web.routes import cards

    _seed_charizard(search_session)

    original_search_cards = cards.pricing.search_cards
    monkeypatch.setattr(cards.pricing, "search_cards", lambda **_: [])
    monkeypatch.setattr(cards, "_ensure_record_assets", lambda *a, **k: False)

    response = cards.search_cards_endpoint(
        query="Sharzard",
        current_user=object(),
        session=search_session,
    )

    assert response.items == []
    assert response.total == 0
    assert response.suggested_query == "Charizard"

    monkeypatch.setattr(cards.pricing, "search_cards", original_search_cards)

    from kartoteka import pricing

    class _DummyResponse:
        status_code = 200

        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    captured = {"called": 0}

    def fake_get(_url, params=None, headers=None, timeout=None):
        captured["called"] += 1
        data = {
            "cards": [
                {
                    "name": "Charizard",
                    "number": "4",
                    "total": "102",
                    "set": {"name": "Base Set", "code": "BS"},
                },
                {
                    "name": "Charoad",
                    "number": "4",
                    "total": "102",
                    "set": {"name": "Base Set", "code": "BS"},
                },
            ]
        }
        return _DummyResponse(data)

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    results = pricing.search_cards(name="Charizard", number="4", limit=10)

    assert captured["called"] == 1
    assert [item["name"] for item in results] == ["Charizard"]


def test_search_cards_allows_typo_without_number(monkeypatch):
    from kartoteka import pricing

    class _DummyResponse:
        status_code = 200

        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    def fake_get(_url, params=None, headers=None, timeout=None):
        data = {
            "cards": [
                {
                    "name": "Charizard",
                    "number": "4",
                    "total": "102",
                    "set": {"name": "Base Set", "code": "BS"},
                },
                {
                    "name": "Pikachu",
                    "number": "25",
                    "set": {"name": "Base Set", "code": "BS"},
                },
            ]
        }
        return _DummyResponse(data)

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    results = pricing.search_cards(name="Charoad", set_name="Base Set", limit=5)

    assert [item["name"] for item in results] == ["Charizard"]


def test_search_cards_sets_default_user_agent(monkeypatch):
    from kartoteka import pricing

    class _DummyResponse:
        status_code = 200

        def json(self):
            return {"cards": []}

    captured: dict[str, dict | None] = {"headers": None}

    def fake_get(_url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _DummyResponse()

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    pricing.search_cards(name="Charizard", number="4", rapidapi_key=None, rapidapi_host=None)

    assert captured["headers"]["User-Agent"] == "kartoteka/1.0"


def test_search_cards_sets_user_agent_for_rapidapi(monkeypatch):
    from kartoteka import pricing

    class _DummyResponse:
        status_code = 200

        def json(self):
            return {"cards": []}

    captured: dict[str, dict | None] = {"headers": None}

    def fake_get(_url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _DummyResponse()

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    pricing.search_cards(
        name="Charizard",
        rapidapi_key="test-key",
        rapidapi_host="example.com",
    )

    assert captured["headers"]["User-Agent"] == "kartoteka/1.0"
    assert captured["headers"]["X-RapidAPI-Key"] == "test-key"
    assert captured["headers"]["X-RapidAPI-Host"] == "example.com"


def test_search_cards_respects_session_user_agent():
    from kartoteka import pricing

    class _DummyResponse:
        status_code = 200

        def json(self):
            return {"cards": []}

    class DummySession:
        def __init__(self):
            self.headers = {"User-Agent": "custom-agent/1.0"}
            self.captured = None

        def get(self, url, params=None, headers=None, timeout=None):
            self.captured = headers
            return _DummyResponse()

    session = DummySession()

    pricing.search_cards(name="Charizard", session=session, rapidapi_key=None, rapidapi_host=None)

    assert session.captured["User-Agent"] == "custom-agent/1.0"
