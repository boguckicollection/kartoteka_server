import datetime as dt
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

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
    monkeypatch.setattr("kartoteka_web.auth.get_password_hash", lambda password: f"hashed:{password}")
    monkeypatch.setattr(
        "kartoteka_web.auth.verify_password",
        lambda plain, hashed: hashed == f"hashed:{plain}",
    )
    monkeypatch.setattr(
        "kartoteka_web.routes.users.get_password_hash",
        lambda password: f"hashed:{password}",
    )
    monkeypatch.setattr(
        "kartoteka_web.routes.users.verify_password",
        lambda plain, hashed: hashed == f"hashed:{plain}",
    )

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


def test_card_info_allows_anonymous_access(api_client):
    client, _prices, _ = api_client
    from kartoteka_web import catalogue, database

    database.init_db()
    with database.session_scope() as session:
        record, _ = catalogue.upsert_card_record(
            session,
            {
                "name": "Pikachu",
                "number": "25",
                "set_name": "Base Set",
                "set_code": "base",
                "rarity": "Common",
            },
        )
        assert record is not None

    res = client.get(
        "/cards/info",
        params={
            "name": "Pikachu",
            "number": "25",
            "set_name": "Base Set",
            "set_code": "base",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["card"]["name"] == "Pikachu"
    assert payload["card"]["number"] == "25"
    assert payload["related"] == []


def test_card_info_authenticated_features_intact(api_client):
    client, _prices, _ = api_client
    token = register_and_login(client, username="brock", password="onix")
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka_web import catalogue, database

    database.init_db()
    with database.session_scope() as session:
        for payload in (
            {
                "name": "Eevee",
                "number": "133",
                "set_name": "Jungle",
                "set_code": "jng",
                "rarity": "Common",
            },
            {
                "name": "Eevee",
                "number": "133",
                "set_name": "Fossil",
                "set_code": "fsl",
                "rarity": "Common",
            },
            {
                "name": "Eevee",
                "number": "133",
                "set_name": "Neo Discovery",
                "set_code": "neo4",
                "rarity": "Common",
            },
        ):
            record, _ = catalogue.upsert_card_record(session, payload)
            assert record is not None

    res = client.get(
        "/cards/info",
        params={
            "name": "Eevee",
            "number": "133",
            "set_name": "Jungle",
            "set_code": "jng",
            "related_limit": 2,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    card = payload["card"]
    assert card["name"] == "Eevee"
    assert card["number"] == "133"
    assert card["set_name"] == "Jungle"
    assert len(payload["related"]) == 2

    entry_payload = {
        "quantity": 1,
        "card": {
            "name": card["name"],
            "number": card["number"],
            "set_name": card["set_name"],
        },
    }
    if card.get("set_code"):
        entry_payload["card"]["set_code"] = card["set_code"]

    res = client.post("/cards/", json=entry_payload, headers=headers)
    assert res.status_code == 201, res.text


def test_user_profile_settings(api_client):
    client, _prices, _ = api_client
    token = register_and_login(client, username="leaf", password="bulbasaur")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.patch(
        "/users/me",
        json={
            "email": "leaf@example.com",
            "avatar_url": "https://example.com/avatar.png",
        },
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["email"] == "leaf@example.com"
    assert payload["avatar_url"] == "https://example.com/avatar.png"

    res = client.patch(
        "/users/me",
        json={"current_password": "bulbasaur", "new_password": "venusaur123"},
        headers=headers,
    )
    assert res.status_code == 200

    res = client.post(
        "/users/login",
        json={"username": "leaf", "password": "venusaur123"},
    )
    assert res.status_code == 200

    res = client.patch(
        "/users/me",
        json={"current_password": "wrong", "new_password": "anotherpass"},
        headers=headers,
    )
    assert res.status_code == 400


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
            "artist": "kodama",
            "series": "Scarlet & Violet",
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
    assert results["total"] == 1
    assert results["page"] == 1
    assert results["page_size"] >= 1
    assert len(results["items"]) == 1
    item = results["items"][0]
    assert item["name"] == "Pikachu"
    assert item["set_name"] == "Base Set"
    assert item["number"] == "25"
    assert "set_icon" in item
    assert item["image_small"] == sample[0]["image_small"]


def test_card_search_query_parameter(api_client):
    client, _prices, _ = api_client
    token = register_and_login(client, username="gio", password="charisma")
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka import pricing
    from kartoteka_web import database, models

    with database.session_scope() as session:
        record = models.CardRecord(
            name="Giovanni's Charisma",
            name_normalized=pricing.normalize("Giovanni's Charisma"),
            number=pricing.sanitize_number("78"),
            number_display="78/132",
            total="132",
            set_name="Gym Challenge",
            set_name_normalized=pricing.normalize("Gym Challenge"),
            set_code="gym",
            set_code_clean="gym",
        )
        session.add(record)
        session.commit()

    res = client.get("/cards/search", params={"query": "giovani 78"}, headers=headers)
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["items"], payload
    assert payload["total"] >= 1
    assert payload["items"][0]["name"] == "Giovanni's Charisma"
    assert payload["items"][0]["number"] == "78"


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
    search_results = [
        sample_card,
        {
            "name": "Pikachu",
            "number": "26",
            "number_display": "26/64",
            "total": "64",
            "set_name": "Jungle",
            "set_code": "jungle",
            "rarity": "Common",
            "image_small": "https://example.com/jungle-pikachu.png",
        },
    ]

    monkeypatch.setattr("kartoteka.pricing.search_cards", lambda *a, **k: search_results)

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
    assert data["related"]
    assert {item["set_name"] for item in data["related"]} == {"Jungle"}
    assert all(item["name"] == "Pikachu" for item in data["related"])


def test_card_info_related_by_character(api_client):
    client, _prices, _ = api_client
    token = register_and_login(client, username="brock", password="onix")
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka import pricing
    from kartoteka_web import database, models
    from kartoteka_web.utils import sets as set_utils

    now = dt.datetime.now(dt.timezone.utc)

    with database.session_scope() as session:
        base_record = models.CardRecord(
            name="Eevee",
            name_normalized=pricing.normalize("Eevee"),
            number=pricing.sanitize_number("11"),
            number_display="11/64",
            total="64",
            set_name="Jungle",
            set_name_normalized=pricing.normalize("Jungle"),
            set_code="jungle",
            set_code_clean=set_utils.clean_code("jungle"),
            rarity="Common",
            artist="Kagemaru Himeno",
            series="Jungle",
            image_small="https://example.com/eevee-jungle.png",
            price_pln=15.5,
            price_updated_at=now,
        )
        alt_record = models.CardRecord(
            name="Eevee",
            name_normalized=pricing.normalize("Eevee"),
            number=pricing.sanitize_number("63"),
            number_display="63/102",
            total="102",
            set_name="Base Set 2",
            set_name_normalized=pricing.normalize("Base Set 2"),
            set_code="base2",
            set_code_clean=set_utils.clean_code("base2"),
            rarity="Common",
            artist="Kagemaru Himeno",
            series="Base Set 2",
            image_small="https://example.com/eevee-base2.png",
            price_pln=12.0,
            price_updated_at=now,
        )
        session.add(base_record)
        session.add(alt_record)

    res = client.get(
        "/cards/info",
        params={"name": "Eevee", "number": "11", "set_name": "Jungle"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["related"], payload
    assert any(item["set_name"] == "Base Set 2" for item in payload["related"])
    assert all(
        pricing.normalize(item["name"]) == pricing.normalize("Eevee")
        for item in payload["related"]
    )


def test_card_detail_page_prefills_dataset(api_client):
    client, _prices, _server = api_client
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka import pricing
    from kartoteka_web import database, models

    with database.session_scope() as session:
        record = models.CardRecord(
            name="Pikachu",
            name_normalized=pricing.normalize("Pikachu"),
            number=pricing.sanitize_number("25"),
            number_display="25/102",
            total="102",
            set_name="Base Set",
            set_name_normalized=pricing.normalize("Base Set"),
            set_code="base",
            set_code_clean="base",
            rarity="Common",
            artist="Mitsuhiro Arita",
            series="Base",
            image_small="https://example.com/pikachu-small.png",
            image_large="https://example.com/pikachu-large.png",
        )
        session.add(record)
        session.commit()

    res = client.get("/cards/base/25", headers=headers)
    assert res.status_code == 200
    html = res.text
    assert 'data-name="Pikachu"' in html
    assert 'data-number="25"' in html
    assert 'data-set-code="base"' in html
    assert 'data-set-name="Base Set"' in html
    assert 'data-total="102"' in html
    assert '<h1 id="card-detail-title">Pikachu</h1>' in html

    # Even when the query provides conflicting metadata, the template should use
    # the canonical catalogue values so the dataset remains consistent.
    res = client.get(
        "/cards/base/25",
        params={"set_name": "151", "set_code": "sv3"},
        headers=headers,
    )
    assert res.status_code == 200
    html = res.text
    assert 'data-set-code="base"' in html
    assert 'data-set-name="Base Set"' in html
    assert 'data-total="102"' in html
    assert 'data-name="Pikachu"' in html


def test_card_info_regression_for_set_slug(api_client, monkeypatch):
    client, prices, _server = api_client
    token = register_and_login(client, username="mew", password="psyduck")
    headers = {"Authorization": f"Bearer {token}"}

    prices["value"] = 42.0

    sample_card = {
        "name": "Mew ex",
        "number": "199",
        "number_display": "199/207",
        "total": "207",
        "set_name": "Scarlet & Violet: 151",
        "set_code": "sv3pt5",
        "rarity": "Ultra Rare",
        "artist": "5ban Graphics",
        "series": "Scarlet & Violet",
        "image_small": "https://example.com/mew-small.png",
        "image_large": "https://example.com/mew-large.png",
        "set_icon": "https://example.com/mew-icon.png",
    }

    calls: list[dict[str, Any]] = []

    def fake_search_cards(*, name, number=None, total=None, set_name=None, limit=None):
        calls.append(
            {
                "name": name,
                "number": number,
                "total": total,
                "set_name": set_name,
                "limit": limit,
            }
        )
        if set_name is None:
            return [sample_card]
        return []

    monkeypatch.setattr("kartoteka.pricing.search_cards", fake_search_cards)

    res = client.get(
        "/cards/mew/199",
        params={"name": "Mew ex", "set_name": "151"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    html = res.text
    assert 'data-set-code="sv3pt5"' in html
    assert 'data-set-name="151"' in html
    assert 'data-name="Mew ex"' in html

    res = client.get(
        "/cards/info",
        params={
            "name": "Mew ex",
            "number": "199",
            "set_name": "151",
            "set_code": "sv3pt5",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["card"]["name"] == "Mew ex"
    assert payload["card"]["set_code"] == "sv3pt5"
    assert payload["card"]["set_name"] == "Scarlet & Violet: 151"
    assert len(calls) >= 2
    assert calls[0]["set_name"] == "151"
    assert calls[-1]["set_name"] is None


def test_card_detail_page_missing_catalogue_returns_404(api_client):
    client, _prices, _server = api_client
    token = register_and_login(client, username="misty", password="staryu")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/cards/base/25", headers=headers)
    assert res.status_code == 404
    assert "Nie znaleziono karty" in res.text
