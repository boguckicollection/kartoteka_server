import asyncio
import sys
from contextlib import suppress
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine, select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    return tmp_path_factory.mktemp("web") / "api.db"


def _configure_test_environment(db_path, monkeypatch):
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("KARTOTEKA_DATABASE_URL", db_url)

    from kartoteka_web import database

    with suppress(Exception):
        database.engine.dispose()
    if db_path.exists():
        db_path.unlink()
    connect_args = {"check_same_thread": False}
    database.engine = create_engine(db_url, echo=False, connect_args=connect_args)

    database.init_db()

    import server

    monkeypatch.setattr(
        "kartoteka_web.services.tcg_api.search_cards", lambda *args, **kwargs: []
    )
    monkeypatch.setattr(
        "kartoteka_web.services.tcg_api.list_set_cards", lambda *args, **kwargs: ([], 0)
    )
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

    return server


@pytest.fixture
def api_client(db_path, monkeypatch):
    server = _configure_test_environment(db_path, monkeypatch)

    with TestClient(server.app) as client:
        yield client, server


def perform_register_and_login(
    client: TestClient,
    username: str = "ash",
    password: str = "pikachu",
    login_username: str | None = None,
) -> str:
    res = client.post(
        "/users/register",
        json={"username": username, "password": password},
    )
    assert res.status_code == 201, res.text

    res = client.post(
        "/users/login",
        json={"username": login_username or username, "password": password},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    assert token
    return token


async def perform_register_and_login_async(
    client: httpx.AsyncClient,
    username: str = "ash",
    password: str = "pikachu",
    login_username: str | None = None,
) -> str:
    res = await client.post(
        "/users/register",
        json={"username": username, "password": password},
    )
    assert res.status_code == 201, res.text

    res = await client.post(
        "/users/login",
        json={"username": login_username or username, "password": password},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    assert token
    return token


def register_and_login(api_client):
    client, _server = api_client
    registration_username = "   ash   "
    login_username = "\tash\n"

    res = client.post(
        "/users/register",
        json={"username": registration_username, "password": "pikachu"},
    )
    assert res.status_code == 201, res.text
    payload = res.json()
    assert payload["username"] == "ash"

    res = client.post(
        "/users/login",
        json={"username": login_username, "password": "pikachu"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]


def test_collection_crud(api_client):
    client, _server = api_client
    token = perform_register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka_web import database, models

    payload = {
        "quantity": 2,
        "purchase_price": 9.99,
        "is_reverse": False,
        "is_holo": False,
        "card": {"name": "Pikachu", "number": "25", "set_name": "Base Set", "set_code": "base"},
    }

    res = client.post("/cards/", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    entry = res.json()
    assert entry["quantity"] == 2
    assert entry["purchase_price"] == 9.99
    assert entry["card"]["name"] == "Pikachu"
    entry_id = entry["id"]

    res = client.get("/cards/", headers=headers)
    assert res.status_code == 200
    cards = res.json()
    assert len(cards) == 1
    assert cards[0]["card"]["name"] == "Pikachu"

    res = client.patch(f"/cards/{entry_id}", json={"quantity": 3}, headers=headers)
    assert res.status_code == 200
    assert res.json()["quantity"] == 3

    with database.session_scope() as session:
        stored = session.exec(select(models.CollectionEntry)).first()
        assert stored is not None
        assert stored.quantity == 3

    res = client.delete(f"/cards/{entry_id}", headers=headers)
    assert res.status_code == 204
    res = client.get("/cards/", headers=headers)
    assert res.json() == []


def test_requires_authentication(api_client):
    client, _server = api_client
    res = client.get("/cards/")
    assert res.status_code == 401

    token = perform_register_and_login(client, username="misty", password="starmie")
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
    client, _server = api_client
    from kartoteka_web import database, models

    database.init_db()
    with database.session_scope() as session:
        session.add(
            models.Card(
                name="Pikachu",
                number="25",
                set_name="Base Set",
                set_code="base",
                rarity="Common",
            )
        )
        session.commit()

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
    client, _server = api_client
    token = perform_register_and_login(client, username="brock", password="onix")
    headers = {"Authorization": f"Bearer {token}"}

    from kartoteka_web import database, models

    database.init_db()
    with database.session_scope() as session:
        for card in (
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
                number="133",
                set_name="Neo Discovery",
                set_code="neo4",
                rarity="Common",
            ),
        ):
            session.add(card)
        session.commit()

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
    client, _server = api_client
    token = perform_register_and_login(client, username="leaf", password="bulbasaur")
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


def test_async_registration_flow(db_path, monkeypatch):
    async def run():
        server = _configure_test_environment(db_path, monkeypatch)

        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            token = await perform_register_and_login_async(client)
            headers = {"Authorization": f"Bearer {token}"}

            payload = {
                "quantity": 1,
                "purchase_price": 5.0,
                "is_reverse": False,
                "is_holo": False,
                "card": {
                    "name": "Bulbasaur",
                    "number": "1",
                    "set_name": "Base Set",
                    "set_code": "base",
                },
            }

            res = await client.post("/cards/", json=payload, headers=headers)
            assert res.status_code == 201, res.text

            res = await client.get("/cards/", headers=headers)
            assert res.status_code == 200
            assert len(res.json()) == 1

    asyncio.run(run())
