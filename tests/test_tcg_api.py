"""Tests for Pokémon TCG API helper utilities."""

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


def test_search_cards_uses_rapidapi_headers(monkeypatch):
    monkeypatch.setattr(tcg_api, "POKEMONTCG_API_URL", "https://api.pokemontcg.io/v2/cards")
    monkeypatch.setattr(tcg_api, "POKEMONTCG_API_KEY", "official-key")

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
    assert "X-Api-Key" not in headers


def test_search_cards_uses_default_host_when_missing(monkeypatch):
    monkeypatch.setattr(tcg_api, "POKEMONTCG_API_URL", "https://api.pokemontcg.io/v2/cards")
    monkeypatch.setattr(tcg_api, "POKEMONTCG_API_KEY", "official-key")

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
    assert "X-Api-Key" not in headers


def test_list_set_cards_uses_rapidapi_headers(monkeypatch):
    monkeypatch.setattr(tcg_api, "POKEMONTCG_API_URL", "https://api.pokemontcg.io/v2/cards")
    monkeypatch.setattr(tcg_api, "POKEMONTCG_API_KEY", "official-key")

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
    assert "X-Api-Key" not in headers
