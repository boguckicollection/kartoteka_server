"""Tests for collection CRUD operations and catalogue endpoints."""

from __future__ import annotations

from sqlmodel import select

from kartoteka_web import database, models


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
            "set_name": "Jungle",
            "set_code": "jng",
            "rarity": "Common",
            "image_small": "https://example.com/eevee-jungle-small.jpg",
            "image_large": "https://example.com/eevee-jungle-large.jpg",
            "set_icon": "https://example.com/jungle.png",
            "artist": "Keiji Kinebuchi",
            "series": "Base",
            "release_date": "1999/06/16",
        },
        {
            "name": "Eevee",
            "number": "133",
            "number_display": "133/151",
            "total": "151",
            "set_name": "Fossil",
            "set_code": "fsl",
            "rarity": "Common",
            "image_small": "https://example.com/eevee-fossil-small.jpg",
            "image_large": "https://example.com/eevee-fossil-large.jpg",
            "set_icon": None,
            "artist": "Mitsuhiro Arita",
            "series": "Base",
            "release_date": "1999/10/10",
        },
    ]

    captured: dict[str, object] = {}

    def fake_search_cards(*, name, number=None, set_name=None, total=None, limit):
        captured.update(
            {
                "name": name,
                "number": number,
                "set_name": set_name,
                "total": total,
                "limit": limit,
            }
        )
        return search_results

    monkeypatch.setattr(
        "kartoteka_web.routes.cards.tcg_api.search_cards",
        fake_search_cards,
    )

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
    assert captured["limit"] == 5
    assert payload["total"] == len(search_results)
    assert payload["suggested_query"] == "Eevee"
    assert {item["set_code"] for item in payload["items"]} == {"jng", "fsl"}

    with database.session_scope() as session:
        session.add_all(
            [
                models.Card(
                    name="Eevee",
                    number="133",
                    set_name="Jungle",
                    set_code="jng",
                    rarity="Common",
                ),
                models.Card(
                    name="Eevee",
                    number="133",
                    set_name="Fossil",
                    set_code="fsl",
                    rarity="Common",
                ),
                models.Card(
                    name="Eevee",
                    number="060",
                    set_name="Base Set",
                    set_code="base",
                    rarity="Common",
                ),
            ]
        )

    info = api_client.get(
        "/cards/info",
        params={
            "name": "Eevee",
            "number": "133",
            "set_name": "Jungle",
            "set_code": "jng",
            "related_limit": 2,
        },
    )
    assert info.status_code == 200, info.text
    detail = info.json()
    assert detail["card"]["set_name"] == "Jungle"
    assert len(detail["related"]) == 2

    missing = api_client.get(
        "/cards/info",
        params={"name": "Missing", "number": "999", "set_name": "Unknown"},
    )
    assert missing.status_code == 404

    unauthenticated_search = api_client.get("/cards/search", params={"query": "Eevee"})
    assert unauthenticated_search.status_code == 401
