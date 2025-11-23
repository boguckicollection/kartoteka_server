"""Tests for collection CRUD operations and catalogue endpoints."""

from __future__ import annotations

import datetime as dt
import importlib

import pytest

from sqlmodel import select

from kartoteka_web import database, models
from kartoteka_web.routes import cards as cards_routes


def _auth_headers(client, username: str = "ash", password: str = "pikachu") -> dict[str, str]:
    register = client.post(
        "/users/register",
        json={"username": username, "password": password},
    )
    assert register.status_code == 201, register.text

    login = client.post(
        "/users/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_collection_crud_lifecycle(api_client):
    headers = _auth_headers(api_client)

    payload = {
        "quantity": 2,
        "purchase_price": 12.5,
        "is_reverse": False,
        "is_holo": True,
        "card": {
            "name": "Pikachu",
            "number": "025",
            "set_name": "Base Set",
            "set_code": "base",
            "rarity": "Common",
            "image_small": "https://example.com/pikachu-small.jpg",
            "image_large": "https://example.com/pikachu-large.jpg",
        },
    }

    created = api_client.post("/cards/", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    entry = created.json()
    assert entry["quantity"] == 2
    assert entry["is_holo"] is True
    assert entry["card"]["name"] == "Pikachu"
    entry_id = entry["id"]

    listing = api_client.get("/cards/", headers=headers)
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["card"]["number"] == "025"

    updated = api_client.patch(
        f"/cards/{entry_id}",
        json={"quantity": 3, "purchase_price": 15.0, "is_reverse": True},
        headers=headers,
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["quantity"] == 3
    assert payload["is_reverse"] is True
    assert payload["purchase_price"] == 15.0

    with database.session_scope() as session:
        stored = session.exec(select(models.CollectionEntry)).first()
        assert stored is not None
        assert stored.quantity == 3
        assert stored.card is not None
        assert stored.card.image_small == "https://example.com/pikachu-small.jpg"

    deleted = api_client.delete(f"/cards/{entry_id}", headers=headers)
    assert deleted.status_code == 204

    empty = api_client.get("/cards/", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []


def test_collection_endpoints_require_authentication(api_client):
    response = api_client.get("/cards/")
    assert response.status_code == 401

    response = api_client.post(
        "/cards/",
        json={"quantity": 1, "card": {"name": "Eevee", "number": "133", "set_name": "Jungle"}},
    )
    assert response.status_code == 401


def test_card_search_and_detail(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="gary", password="eevee")

    search_results = [
        {
            "name": "Eevee",
            "number": "133",
            "number_display": "133/151",
            "total": "151",
            "set_name": "Base Set",
            "set_code": "base1",
            "rarity": "Common",
            "image_small": "https://example.com/eevee-jungle-small.jpg",
            "image_large": "https://example.com/eevee-jungle-large.jpg",
            "set_icon": "https://example.com/jungle.png",
            "artist": "Keiji Kinebuchi",
            "series": "Base",
            "release_date": "1999/06/16",
            "price": 12.34,
            "price_7d_average": 11.11,
            "id": "jng-133",
            "description": "Opis testowy karty",
            "shop_url": "https://example.com/shop/jungle",
        },
        {
            "name": "Eevee",
            "number": "133",
            "number_display": "133/151",
            "total": "151",
            "set_name": "Base Set 2",
            "set_code": "base2",
            "rarity": "Common",
            "image_small": "https://example.com/eevee-fossil-small.jpg",
            "image_large": "https://example.com/eevee-fossil-large.jpg",
            "set_icon": None,
            "artist": "Mitsuhiro Arita",
            "series": "Base",
            "release_date": "1999/10/10",
            "price": 8.5,
            "price_7d_average": 7.25,
            "id": "fsl-133",
        },
    ]

    captured: dict[str, object] = {}

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        captured.update(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "set_code": set_code,
                "total": total,
                "limit": limit,
                "sort": sort,
                "order": order,
                "page": page,
                "per_page": per_page,
                "rapidapi_key": rapidapi_key,
                "rapidapi_host": rapidapi_host,
            }
        )
        if name and "missing" in name.lower():
            return [], 0, 0
        return search_results, len(search_results), 84

    monkeypatch.setattr(
        "kartoteka_web.routes.cards.tcg_api.search_cards",
        fake_search_cards,
    )

    price_history_payload = [
        {"date": "2024-01-01", "marketPrice": 10.0, "currency": "EUR"},
        {"date": "2024-01-05", "marketPrice": 12.5, "currency": "EUR"},
        {"date": "2024-01-10", "marketPrice": 9.75, "currency": "EUR"},
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "fetch_card_price_history",
        lambda *args, **kwargs: price_history_payload,
    )
    monkeypatch.setattr(cards_routes.tcg_api, "get_eur_pln_rate", lambda: 4.0)

    with database.session_scope() as session:
        assert session.exec(select(models.Card)).all() == []

    search = api_client.get(
        "/cards/search",
        params={"query": "Eevee 133", "limit": 5},
        headers=headers,
    )
    assert search.status_code == 200, search.text
    payload = search.json()
    assert captured["name"].startswith("Eevee")
    assert captured["number"] == "133"
    assert captured["sort"] is None
    assert captured["order"] is None
    assert captured["page"] == 1
    assert captured["per_page"] == 20
    assert payload["total"] == len(search_results)
    assert payload["total_count"] == len(search_results)
    assert payload["total_remote"] == 84
    assert payload["page"] == 1
    assert payload["per_page"] == 20
    assert payload["suggested_query"] == "Eevee"
    assert {item["set_code"] for item in payload["items"]} == {"base1", "base2"}
    assert sorted(item["price"] for item in payload["items"]) == [8.5, 12.34]
    assert sorted(item["price_7d_average"] for item in payload["items"]) == [7.25, 11.11]
    icon_map = {item["set_code"]: item["set_icon_path"] for item in payload["items"]}
    assert icon_map["base1"] == "/icon/set/base1.png"
    assert icon_map["base2"] == "/icon/set/base2.png"

    with database.session_scope() as session:
        session.add_all(
            [
                models.Card(
                    name="Eevee",
                    number="133",
                    set_name="Base Set",
                    set_code="base1",
                    rarity="Common",
                ),
                models.Card(
                    name="Eevee",
                    number="133",
                    set_name="Base Set 2",
                    set_code="base2",
                    rarity="Common",
                ),
                models.Card(
                    name="Eevee",
                    number="060",
                    set_name="Base Set 3",
                    set_code="base3",
                    rarity="Common",
                ),
            ]
        )

    info = api_client.get(
        "/cards/info",
        params={
            "name": "Eevee",
            "number": "133",
            "set_name": "Base Set",
            "set_code": "base1",
            "related_limit": 2,
        },
    )
    assert info.status_code == 200, info.text
    detail = info.json()
    assert detail["card"]["set_name"] == "Base Set"
    assert detail["card"]["set_icon_path"] == "/icon/set/base1.png"
    assert detail["card"]["shop_url"] == "https://example.com/shop/jungle"
    assert detail["card"]["description"] == "Opis testowy karty"
    history = detail["card"]["price_history"]
    assert history["all"]
    assert len(history["all"]) == 3
    assert len(history["last_7"]) == 3
    assert len(history["last_30"]) == 3
    assert history["all"][0]["currency"] == "PLN"
    assert history["all"][0]["price"] == pytest.approx(10.0 * 4.0 * 1.24, rel=1e-3)
    assert len(detail["related"]) == 2
    related_icons = {item["set_code"]: item["set_icon_path"] for item in detail["related"]}
    assert related_icons["base2"] == "/icon/set/base2.png"
    assert related_icons["base3"] == "/icon/set/base3.png"

    missing = api_client.get(
        "/cards/info",
        params={"name": "Missing", "number": "999", "set_name": "Unknown"},
    )
    assert missing.status_code == 404

    # Card search is now accessible without authentication
    unauthenticated_search = api_client.get("/cards/search", params={"query": "Eevee"})
    assert unauthenticated_search.status_code == 200  # Changed from 401 to 200


def test_card_info_remote_fallback(api_client, monkeypatch):
    remote_cards = [
        {
            "id": "base1-4",
            "name": "Charizard",
            "number": "4",
            "number_display": "4/102",
            "total": "102",
            "set_name": "Base Set",
            "set_code": "base1",
            "rarity": "Rare Holo",
            "image_small": "https://example.com/charizard-small.jpg",
            "image_large": "https://example.com/charizard-large.jpg",
            "set_icon": "https://example.com/base-set.png",
            "artist": "Mitsuhiro Arita",
            "series": "Base",
            "release_date": "1999/01/09",
            "price": 123.45,
            "price_7d_average": 120.0,
            "description": "Opis zdalnej karty",
            "shop_url": "https://example.com/shop/charizard",
        },
        {
            "id": "base1-5",
            "name": "Charizard",
            "number": "5",
            "number_display": "5/102",
            "total": "102",
            "set_name": "Base Set",
            "set_code": "base1",
            "rarity": "Rare",
            "image_small": "https://example.com/charizard-5-small.jpg",
            "image_large": "https://example.com/charizard-5-large.jpg",
        },
    ]

    captured: dict[str, object] = {}

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit=None,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        captured.update(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "set_code": set_code,
                "total": total,
                "limit": limit,
                "per_page": per_page,
                "rapidapi_key": rapidapi_key,
                "rapidapi_host": rapidapi_host,
            }
        )
        return remote_cards, len(remote_cards), len(remote_cards)

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)

    price_history_payload = [
        {"date": "2024-01-01", "marketPrice": 10.0, "currency": "EUR"},
        {"date": "2024-01-02", "marketPrice": 12.0, "currency": "EUR"},
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "fetch_card_price_history",
        lambda *args, **kwargs: price_history_payload,
    )
    monkeypatch.setattr(cards_routes.tcg_api, "get_eur_pln_rate", lambda: 4.0)

    response = api_client.get(
        "/cards/info",
        params={
            "name": "Charizard",
            "number": "004",
            "set_name": "Base Set",
            "set_code": "base1",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    card = payload["card"]
    assert card["name"] == "Charizard"
    assert card["set_code"] == "base1"
    assert card["price"] == pytest.approx(123.45)
    assert card["number_display"] == "4/102"
    history = card["price_history"]
    assert history["all"], "Expected remote price history to be populated"
    assert captured["set_code"] == "base1"
    assert payload["related"], "Expected related cards from remote search"
    assert payload["related"][0]["number"] == "5"

    with database.session_scope() as session:
        assert session.exec(select(models.Card)).all() == []


def test_card_info_remote_skip_when_numbers_conflict(api_client, monkeypatch):
    with database.session_scope() as session:
        session.add(
            models.Card(
                name="Eevee",
                number="133",
                set_name="Base Set",
                set_code="base1",
                rarity="Common",
            )
        )

    remote_cards = [
        {
            "id": "base2-200",
            "name": "Eevee",
            "number": "200",
            "number_display": "200/151",
            "total": "151",
            "set_name": "Base Set 2",
            "set_code": "base2",
            "rarity": "Rare",
            "price": 99.99,
        }
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "search_cards",
        lambda *args, **kwargs: (remote_cards, len(remote_cards), len(remote_cards)),
    )

    response = api_client.get(
        "/cards/info",
        params={
            "name": "Eevee",
            "number": "133",
            "set_name": "Base Set",
            "set_code": "base1",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    card = payload["card"]
    assert card["number"] == "133"
    assert card["number_display"] == "133"
    assert card["set_code"] == "base1"
    assert card.get("price") is None
    assert payload["related"] == []

def test_card_info_price_history_bounded_then_fallback(api_client, monkeypatch):
    today = dt.date.today()
    remote_cards = [
        {
            "id": "base1-7",
            "name": "Squirtle",
            "number": "7",
            "number_display": "7/102",
            "total": "102",
            "set_name": "Base Set",
            "set_code": "base1",
            "rarity": "Common",
            "image_small": "https://example.com/squirtle-small.jpg",
            "image_large": "https://example.com/squirtle-large.jpg",
        }
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "search_cards",
        lambda **kwargs: (remote_cards, len(remote_cards), len(remote_cards)),
    )

    history_calls: list[dict[str, object]] = []

    def fake_fetch_history(card_id, *, date_from=None, date_to=None, **kwargs):
        history_calls.append({"date_from": date_from, "date_to": date_to})
        if len(history_calls) == 1:
            return []
        return [
            {"date": "2023-12-01", "marketPrice": 5.0, "currency": "EUR"},
            {"date": "2024-01-01", "marketPrice": 6.5, "currency": "EUR"},
        ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "fetch_card_price_history",
        fake_fetch_history,
    )
    monkeypatch.setattr(cards_routes.tcg_api, "get_eur_pln_rate", lambda: 4.0)

    response = api_client.get(
        "/cards/info",
        params={
            "name": "Squirtle",
            "number": "7",
            "set_name": "Base Set",
            "set_code": "base1",
            "date_from": (today - dt.timedelta(days=30)).isoformat(),
            "date_to": today.isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    history = payload["card"]["price_history"]
    assert history["all"], "Expected fallback history to populate price history"
    assert history["last_30"], "Expected 30-day slice after fallback"
    assert len(history["all"]) == 2
    assert len(history_calls) == 2
    assert isinstance(history_calls[0]["date_from"], dt.date)
    assert history_calls[1]["date_from"] is None
    assert history_calls[1]["date_to"] is None


def test_card_info_remote_fallback_without_set_filters(api_client, monkeypatch):
    remote_payload = {
        "id": "sv1-12",
        "name": "Pikachu",
        "number": "12",
        "number_display": "012/190",
        "total": "190",
        "set_name": "Scarlet & Violet",
        "set_code": "sv1",
        "rarity": "Common",
        "image_small": "https://example.com/pikachu-small.jpg",
        "image_large": "https://example.com/pikachu-large.jpg",
    }

    attempts: list[tuple[str | None, str | None, str | None]] = []

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit=None,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        attempts.append((number, set_name, set_code))
        if set_code or set_name:
            return [], 0, 0
        return [remote_payload], 1, 1

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)
    monkeypatch.setattr(
        cards_routes.tcg_api, "fetch_card_price_history", lambda *args, **kwargs: []
    )

    response = api_client.get(
        "/cards/info",
        params={
            "name": "Pikachu",
            "number": "12",
            "set_name": "Scarlet & Violet",
            "set_code": "sv1",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["card"]["name"] == "Pikachu"
    assert payload["card"]["set_code"] == "sv1"
    assert payload["related"] == []
    assert payload["card"]["image_small"] == remote_payload["image_small"]
    assert payload["card"]["image_large"] == remote_payload["image_large"]

    assert len(attempts) >= 3
    # Initial query retains the provided number and set filters.
    assert attempts[0] == ("12", "Scarlet & Violet", "sv1")
    # First retry drops the number but still carries the set filters.
    assert attempts[1] == (None, "Scarlet & Violet", "sv1")
    # Final retry removes the set filters entirely, allowing the remote result.
    assert attempts[-1] == (None, None, None)


def test_card_info_retries_without_number(api_client, monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit=None,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        calls.append(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "set_code": set_code,
                "total": total,
                "limit": limit,
                "per_page": per_page,
            }
        )
        if number == "146":
            return [], 0, 0
        return (
            [
                {
                    "id": "basep-h1",
                    "name": "Zapdos",
                    "number": "H1",
                    "number_display": "H1",
                    "set_name": "Wizards Black Star Promos",
                    "set_code": "basep",
                    "rarity": "Promo",
                    "image_small": "https://example.com/zapdos-small.jpg",
                    "image_large": "https://example.com/zapdos-large.jpg",
                    "price": 9.99,
                }
            ],
            1,
            1,
        )

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)
    monkeypatch.setattr(cards_routes.tcg_api, "fetch_card_price_history", lambda *_, **__: [])
    monkeypatch.setattr(cards_routes.tcg_api, "get_eur_pln_rate", lambda: 4.0)

    response = api_client.get(
        "/cards/info",
        params={
            "name": "Zapdos",
            "number": "146",
            "set_name": "Wizards Black Star Promos",
            "set_code": "basep",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    card = payload["card"]
    assert card["number_display"] == "H1"
    assert card["name"] == "Zapdos"
    assert card["image_small"] == "https://example.com/zapdos-small.jpg"
    assert card["price"] == pytest.approx(9.99)

    assert len(calls) == 2
    assert calls[0]["number"] == "146"
    assert calls[1]["number"] is None
    assert calls[1]["total"] is None

def test_card_info_accepts_normalized_set_code(api_client):
    with database.session_scope() as session:
        session.add(
            models.Card(
                name="Charizard",
                number="4",
                set_name="Base Set",
                set_code="UPPER-SET",
                rarity="Rare",
            )
        )

    response = api_client.get(
        "/cards/info",
        params={
            "name": "Charizard",
            "number": "4",
            "set_code": "upper-set",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["card"]["set_code"] == "UPPER-SET"


def test_card_info_uses_month_range_by_default(api_client, monkeypatch):
    class _FixedDate(dt.date):
        @classmethod
        def today(cls):  # pragma: no cover - patched for deterministic range
            return cls(2024, 2, 15)

    monkeypatch.setattr(cards_routes.dt, "date", _FixedDate)

    remote_results = [
        {
            "id": "sv1-1",
            "name": "Pikachu",
            "number": "001",
            "set_name": "Scarlet & Violet",
            "set_code": "sv1",
            "price": 9.99,
        }
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "search_cards",
        lambda **_: (remote_results, len(remote_results), len(remote_results)),
    )

    captured_calls: list[dict[str, object]] = []

    def fake_history(card_id, **kwargs):
        captured_calls.append({"card_id": card_id, "kwargs": kwargs})
        return []

    monkeypatch.setattr(cards_routes.tcg_api, "fetch_card_price_history", fake_history)

    response = api_client.get(
        "/cards/info",
        params={"name": "Pikachu", "number": "001"},
    )

    assert response.status_code == 200, response.text
    assert captured_calls, "Expected price history requests to be made"
    first_call = captured_calls[0]
    assert first_call.get("card_id") == "sv1-1"
    params = first_call.get("kwargs") or {}
    assert params.get("date_from") == dt.date(2024, 1, 16)
    assert params.get("date_to") == dt.date(2024, 2, 15)


def test_card_info_price_history_section_visible_when_data_present(
    api_client, monkeypatch
):
    remote_results = [
        {
            "id": "sv1-001",
            "name": "Pikachu",
            "number": "001",
            "set_name": "Scarlet & Violet",
            "set_code": "sv1",
        }
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "search_cards",
        lambda **_: (remote_results, len(remote_results), len(remote_results)),
    )

    price_history_payload = [
        {"date": "2024-01-01", "marketPrice": 7.5, "currency": "EUR"},
        {"date": "2024-01-15", "marketPrice": 8.25, "currency": "EUR"},
    ]

    monkeypatch.setattr(
        cards_routes.tcg_api,
        "fetch_card_price_history",
        lambda *_, **__: price_history_payload,
    )
    monkeypatch.setattr(cards_routes.tcg_api, "get_eur_pln_rate", lambda: 4.0)

    response = api_client.get(
        "/cards/info",
        params={"name": "Pikachu", "number": "001", "set_name": "Scarlet & Violet"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    history = payload["card"]["price_history"]
    assert history["all"], "Expected chart data to be available"
    assert history["last_30"], "Expected month range data for chart"
    assert all(point["currency"] == "PLN" for point in history["all"])


def test_card_search_passes_rapidapi_credentials(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="misty", password="starmie")

    captured: dict[str, object] = {}

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        captured.update(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "set_code": set_code,
                "total": total,
                "limit": limit,
                "sort": sort,
                "order": order,
                "page": page,
                "per_page": per_page,
                "rapidapi_key": rapidapi_key,
                "rapidapi_host": rapidapi_host,
            }
        )
        return [], 0, 0

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)
    monkeypatch.setattr(cards_routes, "RAPIDAPI_KEY", "rapid-key")
    monkeypatch.setattr(cards_routes, "RAPIDAPI_HOST", "rapid.example.com")

    response = api_client.get(
        "/cards/search",
        params={"query": "Starmie", "sort": "price", "order": "desc"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert captured["rapidapi_key"] == "rapid-key"
    assert captured["rapidapi_host"] == "rapid.example.com"
    assert captured["name"].startswith("Starmie")
    assert captured["sort"] == "price"
    assert captured["order"] == "desc"
    assert captured["page"] == 1
    assert captured["per_page"] == 20


def test_cards_module_uses_generic_rapidapi_env(monkeypatch):
    for variable in (
        "KARTOTEKA_RAPIDAPI_KEY",
        "POKEMONTCG_RAPIDAPI_KEY",
        "KARTOTEKA_RAPIDAPI_HOST",
        "POKEMONTCG_RAPIDAPI_HOST",
    ):
        monkeypatch.delenv(variable, raising=False)

    monkeypatch.setenv("RAPIDAPI_KEY", "generic-rapid-key")
    monkeypatch.setenv("RAPIDAPI_HOST", "generic-rapid.example.com")

    reloaded_cards = importlib.reload(cards_routes)

    captured: dict[str, object] = {}

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        captured.update(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "set_code": set_code,
                "total": total,
                "limit": limit,
                "sort": sort,
                "order": order,
                "page": page,
                "per_page": per_page,
                "rapidapi_key": rapidapi_key,
                "rapidapi_host": rapidapi_host,
            }
        )
        return [], 0, 0

    monkeypatch.setattr(reloaded_cards.tcg_api, "search_cards", fake_search_cards)

    dummy_user = models.User(id=1, username="misty", hashed_password="hashed:pw")

    database.init_db()
    with database.session_scope() as session:
        response = reloaded_cards.search_cards_endpoint(
            query="Eevee",
            limit=5,
            current_user=dummy_user,
            session=session,
            set_code=None,
        )

    assert response.total == 0
    assert response.total_count == 0
    assert captured["rapidapi_key"] == "generic-rapid-key"
    assert captured["rapidapi_host"] == "generic-rapid.example.com"
    assert captured["page"] == 1
    assert captured["per_page"] == 20


def test_card_search_pagination_clamping(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="brock", password="onix")

    captured: dict[str, object] = {}

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit=None,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        captured.update(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "set_code": set_code,
                "total": total,
                "limit": limit,
                "sort": sort,
                "order": order,
                "page": page,
                "per_page": per_page,
                "rapidapi_key": rapidapi_key,
                "rapidapi_host": rapidapi_host,
            }
        )
        return [], 0, 150

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)

    response = api_client.get(
        "/cards/search",
        params={"query": "Onix", "page": 9, "per_page": 50},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert captured["page"] == 1
    assert captured["per_page"] == 20
    assert captured["limit"] == 100
    assert payload["page"] == 1
    assert payload["per_page"] == 20


def test_card_search_prefers_local_catalog(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="sabrina", password="alakazam")

    def _fail_remote(**_: object) -> None:
        raise AssertionError("Remote search should not be invoked when local data exists")

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", _fail_remote)

    with database.session_scope() as session:
        session.add(
            models.CardRecord(
                name="Charizard",
                name_normalized="charizard",
                number="4",
                number_display="004/102",
                total="102",
                set_name="Base Set",
                set_name_normalized="base set",
                set_code="base1",
                set_code_clean="base1",
                rarity="Rare Holo",
                image_small="https://example.com/charizard-small.jpg",
                image_large="https://example.com/charizard-large.jpg",
                price=120.0,
                price_7d_average=115.5,
            )
        )

    response = api_client.get(
        "/cards/search",
        params={"query": "Charizard"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["total_count"] == 1
    assert payload["items"][0]["name"] == "Charizard"
    assert payload["items"][0]["set_name"] == "Base Set"


def test_card_search_populates_catalog_from_remote(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="janine", password="arbok")

    captured_records: list[dict[str, object]] = [
        {
            "name": "Mewtwo",
            "number": "10",
            "set_name": "Legendary Collection",
            "set_code": "lc",
            "price": 42.0,
        }
    ]

    def fake_search_cards(**kwargs):  # noqa: ANN001
        assert kwargs["name"].startswith("Mewtwo")
        return captured_records, len(captured_records), len(captured_records)

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)

    response = api_client.get(
        "/cards/search",
        params={"query": "Mewtwo"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Mewtwo"

    with database.session_scope() as session:
        stored = session.exec(
            select(models.CardRecord).where(models.CardRecord.name == "Mewtwo")
        ).first()
        assert stored is not None
        assert stored.set_code == "lc"
        assert payload["total_count"] == 1
        assert payload["total_remote"] == 1


def test_card_search_uses_filtered_total_for_pagination(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="janine", password="ariados")

    filtered_records = [
        {
            "name": "Mew",
            "number": "001",
            "number_display": "1/20",
            "total": "20",
            "set_name": "Mythical Collection",
            "set_code": "mythic",
            "rarity": "Rare",
            "image_small": None,
            "image_large": None,
        },
        {
            "name": "Mew",
            "number": "002",
            "number_display": "2/20",
            "total": "20",
            "set_name": "Mythical Collection",
            "set_code": "mythic",
            "rarity": "Rare",
            "image_small": None,
            "image_large": None,
        },
        {
            "name": "Mew",
            "number": "003",
            "number_display": "3/20",
            "total": "20",
            "set_name": "Mythical Collection",
            "set_code": "mythic",
            "rarity": "Rare",
            "image_small": None,
            "image_large": None,
        },
    ]

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit=None,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        return filtered_records, len(filtered_records), 80

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)

    response = api_client.get(
        "/cards/search",
        params={"query": "Mew", "page": 5, "per_page": 2},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["page"] == 2
    assert payload["per_page"] == 2
    assert payload["total"] == 1
    assert payload["total_count"] == len(filtered_records)
    assert payload["total_remote"] == 80
    assert [item["number"] for item in payload["items"]] == ["003"]


def test_card_search_uses_local_pagination(api_client, monkeypatch):
    headers = _auth_headers(api_client, username="sabrina", password="alakazam")

    captured: dict[str, object] = {}

    records = [
        {
            "name": f"Pikachu {index:03d}",
            "number": f"{index:03d}",
            "number_display": f"{index:03d}",
            "total": None,
            "set_name": "Base Set",
            "set_code": f"base{index % 5}",
            "rarity": "Common",
            "image_small": None,
            "image_large": None,
            "set_icon": None,
            "artist": None,
            "series": None,
            "release_date": None,
            "price": None,
        }
        for index in range(1, 101)
    ]

    def fake_search_cards(
        *,
        name,
        number=None,
        set_name=None,
        set_code=None,
        total=None,
        limit=None,
        sort=None,
        order=None,
        page=None,
        per_page=None,
        rapidapi_key=None,
        rapidapi_host=None,
    ):
        captured.update(
            {
                "name": name,
                "set_code": set_code,
                "limit": limit,
                "page": page,
                "per_page": per_page,
            }
        )
        return records, len(records), 100

    monkeypatch.setattr(cards_routes.tcg_api, "search_cards", fake_search_cards)

    response = api_client.get(
        "/cards/search",
        params={"query": "Pikachu", "page": 3, "per_page": 20},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert captured["limit"] == 100
    assert captured["page"] == 1
    assert payload["page"] == 3
    assert payload["per_page"] == 20
    assert payload["total"] == 20
    assert payload["total_count"] == len(records)
    assert payload["total_remote"] == 100
    returned_numbers = [item["number"] for item in payload["items"]]
    assert returned_numbers[0] == "041"
    assert returned_numbers[-1] == "060"
