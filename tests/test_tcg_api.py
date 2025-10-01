"""Tests for RapidAPI Pokémon TCG helper utilities."""

from __future__ import annotations

from kartoteka_web.services import tcg_api


class _DummySession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.headers = {"User-Agent": "pytest-agent"}

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
            status_code = 200

            @staticmethod
            def json():
                return {"data": []}

        return _Response()


def test_search_cards_uses_rapidapi_headers():
    session = _DummySession()
    tcg_api.search_cards(
        name="Pikachu",
        rapidapi_key="rapid-key",
        rapidapi_host="pokemon-tcg.p.rapidapi.com",
        session=session,
    )

    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg.p.rapidapi.com/v2/cards"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == "pokemon-tcg.p.rapidapi.com"
    params = call["params"] or {}
    assert "search" in params
    assert params["search"] == "pikachu"


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
    assert call["url"] == "https://pokemon-tcg.p.rapidapi.com/v2/cards"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == "pokemon-tcg.p.rapidapi.com"
    params = call["params"] or {}
    assert "search" in params
    assert params["search"] == "eevee"


def test_search_cards_without_key_omits_auth_header():
    session = _DummySession()
    tcg_api.search_cards(name="Ditto", rapidapi_host="pokemon-tcg.p.rapidapi.com", session=session)

    assert session.calls, "Expected a single HTTP request"
    call = session.calls[0]
    headers = call["headers"]
    assert "X-RapidAPI-Key" not in headers
    assert headers.get("X-RapidAPI-Host") == "pokemon-tcg.p.rapidapi.com"
    params = call["params"] or {}
    assert params.get("search") == "ditto"


def test_list_set_cards_uses_rapidapi_headers():
    session = _DummySession()
    cards, request_count = tcg_api.list_set_cards(
        "base",
        limit=1,
        rapidapi_key="rapid-key",
        rapidapi_host="pokemon-tcg.p.rapidapi.com",
        session=session,
    )

    assert cards == []
    assert request_count == 1
    assert session.calls, "Expected at least one HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg.p.rapidapi.com/v2/cards"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == "pokemon-tcg.p.rapidapi.com"
    params = call["params"] or {}
    assert "search" in params
    query = params["search"]
    assert 'setId:"base"' in query
    assert 'setPtcgoCode:"base"' in query
    assert 'setName:"*base*"' in query


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


def test_list_set_cards_without_key_uses_default_headers():
    session = _DummySession()
    tcg_api.list_set_cards("base", limit=1, session=session)

    assert session.calls, "Expected at least one HTTP request"
    call = session.calls[0]
    assert call["url"] == "https://pokemon-tcg.p.rapidapi.com/v2/cards"
    headers = call["headers"]
    assert "X-RapidAPI-Key" not in headers
    assert headers.get("X-RapidAPI-Host") == "pokemon-tcg.p.rapidapi.com"
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
    assert call["url"] == "https://pokemon-tcg.p.rapidapi.com/v2/cards"
    headers = call["headers"]
    assert headers.get("X-RapidAPI-Key") == "rapid-key"
    assert headers.get("X-RapidAPI-Host") == "pokemon-tcg.p.rapidapi.com"
