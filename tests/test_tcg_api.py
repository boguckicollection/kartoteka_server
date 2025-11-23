"""Tests for RapidAPI Pokémon TCG helper utilities."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from kartoteka_web.services import tcg_api


class MockDate(dt.date):
    @classmethod
    def today(cls):
        return dt.date(2025, 11, 14)


class _DummySession:
    def __init__(
        self,
        response_data: Any | None = None,
        status_code: int = 200,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self.headers = {"User-Agent": "pytest-agent"}
        self._response_data = response_data or {"data": []}
        self._status_code = status_code

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers or {},
                "timeout": timeout,
            }
        )

        class _Response:
            def __init__(self, data: Any, status_code: int) -> None:
                self._data = data
                self.status_code = status_code

            def json(self):
                return self._data

        return _Response(self._response_data, self._status_code)


DEFAULT_HOST = tcg_api.RAPIDAPI_DEFAULT_HOST


class _PagingSession:
    def __init__(self, pages: list[dict[str, Any]]):
        self.pages = pages
        self.calls: list[dict[str, object]] = []
        self.headers = {"User-Agent": "pytest-agent"}

    def get(self, url, params=None, headers=None, timeout=None):
        call_index = len(self.calls)
        payload = self.pages[call_index] if call_index < len(self.pages) else {"data": []}
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers or {},
                "timeout": timeout,
            }
        )

        class _Response:
            def __init__(self, data: Any) -> None:
                self._data = data
                self.status_code = 200

            def json(self):
                return self._data

        return _Response(payload)


def test_search_cards_uses_rapidapi_headers():
    session = _DummySession()
    results, filtered_total, total_count = tcg_api.search_cards(
        name="Pikachu",
        rapidapi_key="rapid-key",
        rapidapi_host=DEFAULT_HOST,
        session=session,
        sort="name",
        order="asc",
    )

    assert results == []
    assert filtered_total == 0
    assert total_count == 0
    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/search"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert "search" in params
    assert params["search"] == "pikachu"
    assert params.get("page") == "1"
    assert params.get("pageSize") == "20"
    assert params.get("sort") == "name"
    assert params.get("order") == "asc"


def test_search_cards_uses_default_host_when_missing():
    session = _DummySession()
    results, filtered_total, total_count = tcg_api.search_cards(
        name="Eevee",
        rapidapi_key="rapid-key",
        rapidapi_host=None,
        session=session,
    )

    assert results == []
    assert filtered_total == 0
    assert total_count == 0
    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/search"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert "search" in params
    assert params["search"] == "eevee"


def test_search_cards_without_key_omits_auth_header():
    session = _DummySession()
    results, filtered_total, total_count = tcg_api.search_cards(
        name="Ditto", rapidapi_host=DEFAULT_HOST, session=session
    )

    assert results == []
    assert filtered_total == 0
    assert total_count == 0
    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    headers = call["headers"]
    assert "X-RapidAPI-Key" not in headers
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert params.get("search") == "ditto"


def test_list_set_cards_uses_rapidapi_headers():
    session = _DummySession()
    cards, request_count = tcg_api.list_set_cards(
        "base",
        limit=1,
        rapidapi_key="rapid-key",
        rapidapi_host=DEFAULT_HOST,
        session=session,
    )

    assert cards == []
    assert request_count == 1
    assert session.calls, "Expected at least one HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert "search" in params
    query = params["search"]
    assert 'setId:"base"' in query
    assert 'setPtcgoCode:"base"' in query
    assert 'setName:"*base*"' in query
    assert params.get("sort") == "number"


def test_search_cards_builds_compound_query():
    session = _DummySession()
    tcg_api.search_cards(
        name="Pikachu",
        set_name="Base",
        total="102/102",
        session=session,
    )

    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    params = call["params"] or {}
    assert params["search"] == "pikachu base 102"


def test_search_cards_uses_canonical_set_code_when_available():
    session = _DummySession()
    tcg_api.search_cards(
        name="Pikachu",
        set_code="SSP",
        session=session,
    )

    call = session.calls[0]
    params = call["params"] or {}
    search_value = params["search"]
    search_parts = search_value.split()
    assert "ssp" in search_parts
    assert "sv8" in search_parts


def test_search_cards_forwards_pagination_params():
    session = _DummySession()
    tcg_api.search_cards(
        name="Pikachu",
        page=3,
        per_page=15,
        session=session,
    )

    call = session.calls[0]
    params = call["params"] or {}
    assert params.get("page") == "3"
    assert params.get("pageSize") == "15"


def test_search_cards_matches_uppercase_collector_number():
    card_payload = {
        "name": "Pikachu",
        "number": "RC5a",
        "set": {"name": "Radiant Collection"},
    }
    session = _DummySession(response_data={"data": [card_payload]})

    results, filtered_total, total_count = tcg_api.search_cards(
        name="Pikachu",
        number="RC5A",
        session=session,
    )

    assert results, "Expected to receive at least one suggestion"
    assert results[0]["number"] == "rc5a"
    assert filtered_total == 1
    assert total_count == 1


def test_search_cards_aggregates_multiple_pages():
    pages: list[dict[str, Any]] = []
    for index in range(3):
        start = index * 50
        cards = []
        for offset in range(50):
            number_value = f"{start + offset + 1:03d}"
            cards.append(
                {
                    "name": "Pikachu",
                    "number": number_value,
                    "set": {
                        "name": "Base Set",
                        "id": f"base-{index}",
                    },
                }
            )
        pages.append({"data": cards, "totalCount": 150})

    session = _PagingSession(pages)
    results, filtered_total, total_count = tcg_api.search_cards(
        name="Pikachu",
        limit=100,
        per_page=50,
        session=session,
    )

    assert len(results) == 100
    assert filtered_total == 100
    assert total_count == 150
    assert len(session.calls) == 2
    assert session.calls[0]["params"]["page"] == "1"
    assert session.calls[1]["params"]["page"] == "2"


def test_search_cards_stops_fetching_when_limit_reached():
    pages = [
        {
            "data": [
                {
                    "name": "Test",
                    "number": str(index),
                    "set": {"name": "Test Set", "code": "TST"},
                    "id": f"test-{index}",
                }
                for index in range(1, 21)
            ],
        },
        {
            "data": [
                {
                    "name": "Test",
                    "number": "21",
                    "set": {"name": "Test Set", "code": "TST"},
                    "id": "test-21",
                }
            ],
        },
    ]
    session = _PagingSession(pages)

    results, filtered_total, total_count = tcg_api.search_cards(
        name="Test",
        limit=7,
        session=session,
    )

    assert len(session.calls) == 1
    assert len(results) == 7
    assert filtered_total == 7
    assert total_count >= 7


def test_list_set_cards_without_key_uses_default_headers():
    session = _DummySession()
    tcg_api.list_set_cards("base", limit=1, session=session)

    assert session.calls, "Expected at least one HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards"
    headers = call["headers"]
    assert "X-RapidAPI-Key" not in headers
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    query = params["search"]
    assert 'setId:"base"' in query
    assert 'setPtcgoCode:"base"' in query
    assert 'setName:"*base*"' in query


def test_list_set_cards_uses_default_host_when_missing():
    session = _DummySession()
    tcg_api.list_set_cards(
        "base",
        limit=1,
        rapidapi_key="rapid-key",
        rapidapi_host=None,
        session=session,
    )

    assert session.calls, "Expected at least one HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST


@pytest.fixture(autouse=True)
def _stub_exchange_rate(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: None)


def test_build_card_payload_extracts_cardmarket_price(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: 4.5)
    card = {
        "name": "Bulbasaur",
        "number": "1/102",
        "set": {"name": "Base Set"},
        "cardmarket": {
            "prices": {
                "averageSellPrice": "9,50",
            }
        },
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["price"] == round(9.5 * 4.5 * 1.24, 2)
    assert payload["price_7d_average"] is None


def test_build_card_payload_prefers_episode_code_for_icon():
    card = {
        "name": "Pikachu",
        "number": "025",
        "set": {
            "name": "Base Set",
            "code": "base1",
            "id": "base-set-001",
        },
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["set_icon_slug"] == "base1"
    assert payload["set_icon_path"] == "/icon/set/base1.png"


def test_build_card_payload_prefers_tcgplayer_price_when_available(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: 4.0)
    card = {
        "name": "Charmander",
        "number": "4/102",
        "set": {"name": "Base Set"},
        "tcgplayer": {
            "prices": {
                "normal": {
                    "market": 3.75,
                }
            }
        },
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["price"] == round(3.75 * 4.0 * 1.24, 2)
    assert payload["price_7d_average"] is None


def test_build_card_payload_skips_price_when_rate_unavailable(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: None)
    card = {
        "name": "Squirtle",
        "number": "7/102",
        "set": {"name": "Base Set"},
        "cardmarket": {"prices": {"averageSellPrice": 2.5}},
        "prices": {"normal": {"7d_average": 1.5}},
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["price"] is None
    assert payload["price_7d_average"] is None


def test_build_card_payload_extracts_7d_average_price(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_rate():
        captured["called"] = captured.get("called", 0) + 1
        return 4.2

    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", fake_rate)

    card = {
        "name": "Pikachu",
        "number": "58/102",
        "set": {"name": "Base Set"},
        "prices": {
            "normal": {
                "7d_average": "2,75",
                "market": 2.4,
            }
        },
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["price_7d_average"] == round(2.75 * 4.2 * 1.24, 2)
    assert payload["price"] == round(2.4 * 4.2 * 1.24, 2)
    assert captured["called"] == 1


def test_build_card_payload_includes_rarity_symbol():
    card = {
        "name": "Pikachu",
        "number": "58/102",
        "set": {"name": "Base Set"},
        "rarity": "Rare Holo",
        "raritySymbol": "https://example.com/rarity.svg",
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["rarity_symbol"] == "/static/icons/rarity/rare-holo.svg"
    assert payload["rarity_symbol_remote"] == "https://example.com/rarity.svg"


def test_build_card_payload_falls_back_to_remote_rarity_symbol_when_unknown():
    card = {
        "name": "Pikachu",
        "number": "58/102",
        "set": {"name": "Base Set"},
        "rarity": "Mystery",  # not present in the local map
        "raritySymbol": "https://example.com/rarity.svg",
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["rarity_symbol"] == "https://example.com/rarity.svg"
    assert payload["rarity_symbol_remote"] == "https://example.com/rarity.svg"


def test_build_card_payload_includes_description_and_shop_url(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: None)
    card = {
        "id": "base1-4",
        "name": "Charizard",
        "number": "4/102",
        "set": {"name": "Base Set"},
        "abilities": [{"name": "Energy Burn", "text": "All Energy attached becomes Fire."}],
        "attacks": [{"name": "Fire Spin", "text": "Discard 2 Energy from Charizard."}],
        "cardmarket": {"url": "https://example.com/cardmarket"},
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert "Energy Burn" in (payload.get("description") or "")
    assert "Fire Spin" in (payload.get("description") or "")
    assert payload.get("shop_url") == "https://example.com/cardmarket"
    assert payload.get("id") == "base1-4"


def test_build_cards_endpoint_supports_nested_paths():
    url = tcg_api._build_cards_endpoint(
        "https://pokemon-tcg-api.p.rapidapi.com",
        "cards",
        "sv1-1",
        "history-prices",
    )
    assert url == "https://pokemon-tcg-api.p.rapidapi.com/cards/sv1-1/history-prices"


def test_fetch_card_price_history_uses_endpoint_and_parses_data():
    history_payload = {
        "data": [
            {"date": "2023-01-01", "market": {"price": 9.99}},
            {"date": "2023-01-02", "market": {"price": 10.5}},
        ]
    }
    session = _DummySession(response_data=history_payload)

    history = tcg_api.fetch_card_price_history(
        "sv1-1",
        rapidapi_key="rapid-key",
        rapidapi_host="https://pokemon-tcg-api.p.rapidapi.com",
        session=session,
        market="tcgplayer",
        date_from=dt.date(2023, 1, 1),
        date_to=dt.date(2023, 1, 31),
    )

    assert session.calls, "Expected a price history request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/sv1-1/history-prices"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert params.get("id") == "sv1-1"
    assert params.get("market") == "tcgplayer"
    assert params.get("date_from") == "2023-01-01"
    assert params.get("date_to") == "2023-01-31"
    assert history == history_payload["data"]


def test_fetch_card_price_history_handles_non_200_response():
    session = _DummySession(status_code=404)

    history = tcg_api.fetch_card_price_history(
        "base1-4",
        rapidapi_key=None,
        rapidapi_host=None,
        session=session,
    )

    assert session.calls, "Expected a price history request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/base1-4/history-prices"
    assert history == []


def test_normalize_price_history_converts_to_pln(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: 4.0)
    history = [
        {"date": "2024-01-01", "marketPrice": 10.0, "currency": "EUR"},
        {"date": "2024-01-02T00:00:00Z", "prices": {"market": 11.0}, "currencyCode": "EUR"},
        {"date": "2024-01-03", "marketPrice": 15.0, "currency": "PLN"},
    ]

    normalized = tcg_api.normalize_price_history(history)

    assert [entry["date"] for entry in normalized] == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
    ]
    assert normalized[0]["price"] == pytest.approx(10.0 * 4.0 * 1.24, rel=1e-3)
    assert normalized[0]["currency"] == "PLN"
    assert normalized[-1]["price"] == pytest.approx(15.0, rel=1e-3)
    assert normalized[-1]["currency"] == "PLN"


def test_slice_price_history_returns_limited_range():
    history = [
        {"date": f"2024-01-{day:02d}", "price": float(day), "currency": "PLN"}
        for day in range(1, 11)
    ]

    sliced = tcg_api.slice_price_history(history, 3)

    assert len(sliced) == 3
    assert [entry["date"] for entry in sliced] == ["2024-01-08", "2024-01-09", "2024-01-10"]


def test_get_latest_products_returns_current_month_and_future_products(monkeypatch):
    """Test that get_latest_products returns products from the current month and future."""
    today = dt.date(2025, 11, 14)
    monkeypatch.setattr(tcg_api.dt, "date", MockDate)

    products_payload = {
        "data": [
            {"name": "Future Product", "releaseDate": "2025-12-01"},
            {"name": "Current Month Product", "releaseDate": "2025-11-15"},
            {"name": "Past Product", "releaseDate": "2025-10-31"},
        ]
    }
    session = _DummySession(response_data=products_payload)

    latest_products = tcg_api.get_latest_products(session=session)

    assert len(latest_products) == 2
    product_names = {p["name"] for p in latest_products}
    assert "Future Product" in product_names
    assert "Current Month Product" in product_names
    assert "Past Product" not in product_names
    # Check sort order (descending)
    assert latest_products[0]["name"] == "Future Product"
    assert latest_products[1]["name"] == "Current Month Product"


def test_get_latest_products_falls_back_to_latest_if_no_current_products(monkeypatch):
    """Test that get_latest_products falls back to the latest products if none are for the current month."""
    today = dt.date(2025, 11, 14)
    monkeypatch.setattr(tcg_api.dt, "date", MockDate)

    products_payload = {
        "data": [
            {"name": "Past Product 1", "releaseDate": "2025-10-31"},
            {"name": "Past Product 2", "releaseDate": "2025-10-30"},
        ]
    }
    session = _DummySession(response_data=products_payload)

    latest_products = tcg_api.get_latest_products(session=session, limit=1)

    assert len(latest_products) == 1
    assert latest_products[0]["name"] == "Past Product 1"