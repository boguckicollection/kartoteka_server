"""Tests for RapidAPI Pokémon TCG helper utilities."""

from __future__ import annotations

from typing import Any

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


def test_search_cards_uses_rapidapi_headers():
    session = _DummySession()
    tcg_api.search_cards(
        name="Pikachu",
        rapidapi_key="rapid-key",
        rapidapi_host=DEFAULT_HOST,
        session=session,
    )

    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/search"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert "q" in params
    assert params["q"] == "pikachu"


def test_search_cards_uses_default_host_when_missing():
    session = _DummySession()
    tcg_api.search_cards(
        name="Eevee",
        rapidapi_key="rapid-key",
        rapidapi_host=None,
        session=session,
    )

    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg-api.p.rapidapi.com/cards/search"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert "q" in params
    assert params["q"] == "eevee"


def test_search_cards_without_key_omits_auth_header():
    session = _DummySession()
    tcg_api.search_cards(name="Ditto", rapidapi_host=DEFAULT_HOST, session=session)

    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    headers = call["headers"]
    assert "X-RapidAPI-Key" not in headers
    assert headers.get("X-RapidAPI-Host") == DEFAULT_HOST
    params = call["params"] or {}
    assert params.get("q") == "ditto"


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
    assert "q" in params
    query = params["q"]
    assert 'setId:"base"' in query
    assert 'setPtcgoCode:"base"' in query
    assert 'setName:"*base*"' in query
    assert params.get("orderBy") == "number"


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
    assert params["q"] == "pikachu base 102"


def test_search_cards_matches_uppercase_collector_number():
    card_payload = {
        "name": "Pikachu",
        "number": "RC5a",
        "set": {"name": "Radiant Collection"},
    }
    session = _DummySession(response_data={"data": [card_payload]})

    results = tcg_api.search_cards(
        name="Pikachu",
        number="RC5A",
        session=session,
    )

    assert results, "Expected to receive at least one suggestion"
    assert results[0]["number"] == "rc5a"


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
    query = params["q"]
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
