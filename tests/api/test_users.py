"""Tests covering user registration, authentication and profile management."""

from __future__ import annotations

from typing import Callable

import pytest


def _register(client, username: str = "ash", password: str = "pikachu", **extra):
    payload = {"username": username, "password": password} | extra
    response = client.post("/users/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, username: str = "ash", password: str = "pikachu") -> str:
    response = client.post("/users/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    token = payload["access_token"]
    assert token
    return token


@pytest.fixture()
def auth_headers(api_client) -> Callable[[str, str], dict[str, str]]:
    def _factory(username: str = "ash", password: str = "pikachu") -> dict[str, str]:
        _register(api_client, username=username, password=password)
        token = _login(api_client, username=username, password=password)
        return {"Authorization": f"Bearer {token}"}

    return _factory


def test_user_registration_and_login_flow(api_client):
    payload = _register(api_client, username="   ash   ", password="pikachu")
    assert payload["username"] == "ash"
    assert payload["email"] is None

    token = _login(api_client, username="ash", password="pikachu")
    headers = {"Authorization": f"Bearer {token}"}

    profile = api_client.get("/users/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["username"] == "ash"


def test_user_profile_updates_and_password_change(api_client, auth_headers):
    headers = auth_headers("misty", "starmie")

    update = api_client.patch(
        "/users/me",
        json={"email": "misty@example.com", "avatar_url": "https://example.com/avatar.png"},
        headers=headers,
    )
    assert update.status_code == 200
    payload = update.json()
    assert payload["email"] == "misty@example.com"
    assert payload["avatar_url"] == "https://example.com/avatar.png"

    bad_password = api_client.patch(
        "/users/me",
        json={"current_password": "wrong", "new_password": "new_secret"},
        headers=headers,
    )
    assert bad_password.status_code == 400

    change_password = api_client.patch(
        "/users/me",
        json={"current_password": "starmie", "new_password": "new_secret"},
        headers=headers,
    )
    assert change_password.status_code == 200

    # Login now requires the updated password.
    res = api_client.post(
        "/users/login",
        json={"username": "misty", "password": "new_secret"},
    )
    assert res.status_code == 200


def test_duplicate_user_registration_rejected(api_client):
    _register(api_client, username="brock", password="onix")

    response = api_client.post(
        "/users/register",
        json={"username": "brock", "password": "geodude"},
    )
    assert response.status_code == 400
    assert "already" in response.json()["detail"].lower()


def test_login_requires_valid_credentials(api_client):
    _register(api_client, username="serena", password="sylveon")

    response = api_client.post(
        "/users/login",
        json={"username": "serena", "password": "wrong"},
    )
    assert response.status_code == 401
