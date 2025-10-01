"""Frontend integration checks for base template theming."""

from __future__ import annotations

from bs4 import BeautifulSoup


def test_base_template_contains_theme_toggle(api_client):
    response = api_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    body = soup.body
    assert body is not None
    assert body.get("data-theme") == "auto"

    toggle = soup.select_one("[data-theme-toggle]")
    assert toggle is not None
    icon = toggle.select_one("[data-theme-toggle-icon]")
    assert icon is not None

    theme_meta = soup.select_one('meta[data-theme-color]')
    assert theme_meta is not None
    assert theme_meta.get("content")
