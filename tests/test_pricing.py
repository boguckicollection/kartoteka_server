import datetime as dt
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kartoteka import pricing


class DummyResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {"rates": [{"mid": 4.5}]}

    def json(self) -> dict:
        return self._payload


def _reset_exchange_cache() -> None:
    pricing._exchange_rate_cache["value"] = None
    pricing._exchange_rate_cache["date"] = None


def test_get_exchange_rate_uses_cache(monkeypatch):
    _reset_exchange_cache()

    monkeypatch.setattr(pricing, "_current_date", lambda: dt.date(2024, 1, 1))

    def fake_get(_url, timeout=None, **_kwargs):
        return DummyResponse(payload={"rates": [{"mid": 4.5}]})

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    first = pricing.get_exchange_rate()
    assert first == 4.5

    def fail_get(*_args, **_kwargs):  # pragma: no cover - defensive
        raise AssertionError("Unexpected HTTP request")

    monkeypatch.setattr(pricing.requests, "get", fail_get)

    second = pricing.get_exchange_rate()
    assert second == 4.5


def test_get_exchange_rate_refreshes_each_day(monkeypatch):
    _reset_exchange_cache()

    payloads = iter([
        {"rates": [{"mid": 4.5}]},
        {"rates": [{"mid": 4.7}]},
    ])

    def fake_get(_url, timeout=None, **_kwargs):
        return DummyResponse(payload=next(payloads))

    current_day = {"value": dt.date(2024, 1, 1)}

    def fake_today():
        return current_day["value"]

    monkeypatch.setattr(pricing, "_current_date", fake_today)
    monkeypatch.setattr(pricing.requests, "get", fake_get)

    initial = pricing.get_exchange_rate()
    assert initial == 4.5

    current_day["value"] = dt.date(2024, 1, 2)
    refreshed = pricing.get_exchange_rate()
    assert refreshed == 4.7


class _DummyHTTPResponse:
    status_code = 200

    def __init__(self, payload: dict | list | None = None):
        self._payload = payload or []

    def json(self):
        return self._payload


def test_fetch_card_price_sets_default_user_agent(monkeypatch):
    captured: dict[str, dict | None] = {"headers": None}

    def fake_get(_url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _DummyHTTPResponse([])

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    pricing.fetch_card_price(
        name="Charizard",
        number="4",
        set_name="Base",
        rapidapi_key=None,
        rapidapi_host=None,
        get_rate=lambda: 4.5,
    )

    assert captured["headers"]["User-Agent"] == "kartoteka/1.0"


def test_fetch_card_price_sets_user_agent_for_rapidapi(monkeypatch):
    captured: dict[str, dict | None] = {"headers": None}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _DummyHTTPResponse({"cards": []})

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    pricing.fetch_card_price(
        name="Charizard",
        number="4",
        set_name="Base",
        rapidapi_key="test-key",
        rapidapi_host="example.com",
        get_rate=lambda: 4.5,
    )

    assert captured["headers"]["User-Agent"] == "kartoteka/1.0"
    assert captured["headers"]["X-RapidAPI-Key"] == "test-key"
    assert captured["headers"]["X-RapidAPI-Host"] == "example.com"


def test_list_set_cards_fetches_all_pages(monkeypatch):
    from kartoteka import pricing

    responses = [
        {
            "data": [
                {
                    "name": "Card A",
                    "number": "1",
                    "set": {"name": "Example", "id": "base1", "total": 3},
                },
                {
                    "name": "Card B",
                    "number": "2",
                    "set": {"name": "Example", "id": "base1", "total": 3},
                },
            ],
            "totalCount": 3,
        },
        {
            "data": [
                {
                    "name": "Card C",
                    "number": "3",
                    "set": {"name": "Example", "id": "base1", "total": 3},
                }
            ],
            "totalCount": 3,
        },
    ]

    captured: list[dict[str, Any]] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.append({
            "url": url,
            "params": params,
            "headers": headers,
        })
        return _DummyHTTPResponse(responses.pop(0))

    monkeypatch.setattr(pricing.requests, "get", fake_get)
    monkeypatch.setattr(pricing, "POKEMONTCG_API_KEY", None)

    results = pricing.list_set_cards("base1", limit=0)

    assert len(results) == 3
    assert [item["number"] for item in results] == ["1", "2", "3"]
    assert len(captured) == 2
    assert captured[0]["url"] == pricing.POKEMONTCG_API_URL
    assert captured[0]["params"]["page"] == "1"
    assert captured[1]["params"]["page"] == "2"
    assert 'set.id:"base1"' in captured[0]["params"]["q"]


def test_list_set_cards_respects_limit(monkeypatch):
    from kartoteka import pricing

    payload = {
        "data": [
            {
                "name": "Card A",
                "number": "10",
                "set": {"name": "Example", "id": "base1", "total": 3},
            },
            {
                "name": "Card B",
                "number": "5",
                "set": {"name": "Example", "id": "base1", "total": 3},
            },
            {
                "name": "Card C",
                "number": "1",
                "set": {"name": "Example", "id": "base1", "total": 3},
            },
        ],
        "totalCount": 3,
    }

    captured = {"params": None}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _DummyHTTPResponse(payload)

    monkeypatch.setattr(pricing.requests, "get", fake_get)
    monkeypatch.setattr(pricing, "POKEMONTCG_API_KEY", None)

    results = pricing.list_set_cards("base1", limit=2)

    assert len(results) == 2
    assert [item["number"] for item in results] == ["1", "5"]
    assert captured["params"]["pageSize"] == "250"


def test_list_set_cards_uses_api_key_header(monkeypatch):
    from kartoteka import pricing

    captured = {"headers": None}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return _DummyHTTPResponse({"data": []})

    monkeypatch.setattr(pricing.requests, "get", fake_get)
    monkeypatch.setattr(pricing, "POKEMONTCG_API_KEY", "secret")

    pricing.list_set_cards("base1", limit=1)

    assert captured["headers"]["X-Api-Key"] == "secret"
    assert captured["headers"]["User-Agent"] == "kartoteka/1.0"


def test_fetch_card_price_respects_session_user_agent():
    class DummySession:
        def __init__(self):
            self.headers = {"User-Agent": "custom-agent/2.0"}
            self.captured = None

        def get(self, url, params=None, headers=None, timeout=None):
            self.captured = headers
            return _DummyHTTPResponse([])

    session = DummySession()

    pricing.fetch_card_price(
        name="Charizard",
        number="4",
        set_name="Base",
        rapidapi_key=None,
        rapidapi_host=None,
        get_rate=lambda: 4.5,
        session=session,
    )

    assert session.captured["User-Agent"] == "custom-agent/2.0"
