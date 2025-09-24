import sys
from contextlib import suppress
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, select


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    return tmp_path_factory.mktemp("web") / "api.db"


@pytest.fixture
def api_client(db_path, monkeypatch):
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("KARTOTEKA_DATABASE_URL", db_url)

    from kartoteka_web import database

    with suppress(Exception):
        database.engine.dispose()
    if db_path.exists():
        db_path.unlink()
    connect_args = {"check_same_thread": False}
    database.engine = create_engine(db_url, echo=False, connect_args=connect_args)

    SQLModel.metadata.create_all(database.engine)

    import server

    prices = {"value": 12.5}

    def fake_price(*_args, **_kwargs):
        return prices["value"]

    monkeypatch.setattr("kartoteka.pricing.fetch_card_price", fake_price)
    monkeypatch.setattr("kartoteka.pricing.search_cards", lambda *a, **k: [])
    monkeypatch.setattr("kartoteka.pricing.list_set_cards", lambda *a, **k: [])
    monkeypatch.setattr("kartoteka_web.utils.images.cache_card_images", lambda payload, **_: payload)
    monkeypatch.setattr("kartoteka_web.utils.images.ensure_local_path", lambda value, **_: value)

    with TestClient(server.app) as client:
        yield client, prices, server


def register_and_login(client: TestClient, username: str = "ash", password: str = "pikachu") -> str:
    res = client.post(
        "/users/register",
        json={"username": username, "password": password},
    )
    assert res.status_code == 201

    res = client.post(
        "/users/login",
        json={"username": username, "password": password},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token
    return token


def test_collection_crud_and_summary(api_client):
    client, prices, server = api_client
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka_web import database, models

    def history_prices():
        with database.session_scope() as session:
            rows = session.exec(
                select(models.PriceHistory.price).order_by(models.PriceHistory.recorded_at)
            ).all()
        return [float(price) for price in rows]

    payload = {
        "quantity": 2,
        "purchase_price": 9.99,
        "is_reverse": False,
        "is_holo": False,
        "card": {"name": "Pikachu", "number": "25", "set_name": "Base Set", "set_code": "base"},
    }

    prices["value"] = 15.0
    res = client.post("/cards/", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    entry = res.json()
    assert entry["current_price"] == 15.0
    entry_id = entry["id"]
    assert history_prices() == [15.0]

    res = client.get("/cards/", headers=headers)
    assert res.status_code == 200
    cards = res.json()
    assert len(cards) == 1
    assert cards[0]["card"]["name"] == "Pikachu"

    res = client.patch(f"/cards/{entry_id}", json={"quantity": 3}, headers=headers)
    assert res.status_code == 200
    assert res.json()["quantity"] == 3

    res = client.get("/cards/summary", headers=headers)
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_cards"] == 1
    assert summary["total_quantity"] == 3

    prices["value"] = 20.0
    res = client.post(f"/cards/{entry_id}/refresh", headers=headers)
    assert res.status_code == 200
    assert res.json()["current_price"] == 20.0
    assert history_prices() == [15.0, 20.0]

    prices["value"] = 25.0
    updated = server._refresh_prices()
    assert updated >= 1
    res = client.get("/cards/", headers=headers)
    assert res.json()[0]["current_price"] == 25.0
    assert history_prices() == [15.0, 20.0, 25.0]

    res = client.delete(f"/cards/{entry_id}", headers=headers)
    assert res.status_code == 204
    res = client.get("/cards/", headers=headers)
    assert res.json() == []


def test_requires_authentication(api_client):
    client, _, _ = api_client
    res = client.get("/cards/")
    assert res.status_code == 401

    token = register_and_login(client, username="misty", password="starmie")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/cards/",
        json={
            "quantity": 1,
            "card": {"name": "Squirtle", "number": "7", "set_name": "Base Set"},
        },
        headers=headers,
    )
    assert res.status_code == 201
    entry_id = res.json()["id"]

    res = client.delete(f"/cards/{entry_id}")
    assert res.status_code == 401


def test_card_search_endpoint(api_client, monkeypatch):
    client, _, _ = api_client
    res = client.get("/cards/search", params={"name": "Pikachu", "number": "25"})
    assert res.status_code == 401

    token = register_and_login(client, username="brock", password="onix")
    headers = {"Authorization": f"Bearer {token}"}

    sample = [
        {
            "name": "Pikachu",
            "number": "25",
            "number_display": "25/102",
            "total": "102",
            "set_name": "Base Set",
            "set_code": "base",
            "rarity": "Common",
            "image_small": "https://example.com/pikachu-small.png",
            "image_large": "https://example.com/pikachu-large.png",
        }
    ]

    monkeypatch.setattr("kartoteka.pricing.search_cards", lambda *a, **k: sample)

    res = client.get(
        "/cards/search",
        params={"name": "Pikachu", "number": "25"},
        headers=headers,
    )
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert results[0]["name"] == "Pikachu"
    assert results[0]["set_name"] == "Base Set"
    assert results[0]["number"] == "25"
    assert "set_icon" in results[0]
    assert results[0]["image_small"] == sample[0]["image_small"]


def test_card_info_endpoint(api_client, monkeypatch):
    client, prices, _ = api_client
    token = register_and_login(client, username="gary", password="eevee")
    headers = {"Authorization": f"Bearer {token}"}

    prices["value"] = 19.75
    payload = {
        "quantity": 1,
        "purchase_price": 9.99,
        "is_reverse": False,
        "is_holo": False,
        "card": {
            "name": "Pikachu",
            "number": "25",
            "set_name": "Base Set",
            "set_code": "base",
        },
    }
    res = client.post("/cards/", json=payload, headers=headers)
    assert res.status_code == 201

    sample_card = {
        "name": "Pikachu",
        "number": "25",
        "number_display": "25/102",
        "total": "102",
        "set_name": "Base Set",
        "set_code": "base",
        "rarity": "Common",
        "artist": "Mitsuhiro Arita",
        "series": "Base",
        "image_small": "https://example.com/pikachu-small.png",
        "image_large": "https://example.com/pikachu-large.png",
        "set_icon": "https://example.com/base-icon.png",
    }
    related_cards = [
        sample_card,
        {
            "name": "Raichu",
            "number": "26",
            "number_display": "26/102",
            "total": "102",
            "set_name": "Base Set",
            "set_code": "base",
            "rarity": "Rare",
            "image_small": "https://example.com/raichu-small.png",
        },
    ]

    monkeypatch.setattr("kartoteka.pricing.search_cards", lambda *a, **k: [sample_card])
    monkeypatch.setattr("kartoteka.pricing.list_set_cards", lambda *a, **k: related_cards)

    res = client.get(
        "/cards/info",
        params={"name": "Pikachu", "number": "25", "set_name": "Base Set"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["card"]["name"] == "Pikachu"
    assert data["card"]["series"] == "Base"
    assert data["card"]["price_pln"] == prices["value"]
    assert len(data["history"]) == 1
    assert data["history"][0]["price"] == prices["value"]
    assert data["related"]
    assert data["related"][0]["name"] == "Raichu"
