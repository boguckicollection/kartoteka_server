"""Tests for RapidAPI Pokémon TCG helper utilities."""

from __future__ import annotations

from typing import Any

import pytest

from kartoteka_web.services import tcg_api


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
    results, total_count = tcg_api.search_cards(
        name="Pikachu",
        rapidapi_key="rapid-key",
        rapidapi_host=DEFAULT_HOST,
        session=session,
        sort="name",
        order="asc",
    )

    assert results == []
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
    results, total_count = tcg_api.search_cards(
        name="Eevee",
        rapidapi_key="rapid-key",
        rapidapi_host=None,
        session=session,
    )

    assert results == []
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
    results, total_count = tcg_api.search_cards(
        name="Ditto", rapidapi_host=DEFAULT_HOST, session=session
    )

    assert results == []
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

    results, total_count = tcg_api.search_cards(
        name="Pikachu",
        number="RC5A",
        session=session,
    )

    assert results, "Expected to receive at least one suggestion"
    assert results[0]["number"] == "rc5a"
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
    results, total_count = tcg_api.search_cards(
        name="Pikachu",
        limit=100,
        per_page=50,
        session=session,
    )

    assert len(results) == 100
    assert total_count == 100
    assert len(session.calls) == 2
    assert session.calls[0]["params"]["page"] == "1"
    assert session.calls[1]["params"]["page"] == "2"


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


def test_build_card_payload_skips_price_when_rate_unavailable(monkeypatch):
    monkeypatch.setattr(tcg_api, "get_eur_pln_rate", lambda: None)
    card = {
        "name": "Squirtle",
        "number": "7/102",
        "set": {"name": "Base Set"},
        "cardmarket": {"prices": {"averageSellPrice": 2.5}},
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["price"] is None


def test_build_card_payload_includes_rarity_symbol():
    card = {
        "name": "Pikachu",
        "number": "58/102",
        "set": {"name": "Base Set"},
        "raritySymbol": "https://example.com/rarity.svg",
    }

    payload = tcg_api.build_card_payload(card)

    assert payload is not None
    assert payload["rarity_symbol"] == "https://example.com/rarity.svg"


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
    )

    assert session.calls, "Expected a price history request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/sv1-1/history-prices"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert params.get("market") == "tcgplayer"
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
