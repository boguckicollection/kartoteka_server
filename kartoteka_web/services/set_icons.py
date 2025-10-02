"""Utilities for fetching and caching official Pokémon TCG set icons."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional

import requests
from requests import Response
from requests.adapters import HTTPAdapter, Retry

from kartoteka_web.utils import sets as set_utils

logger = logging.getLogger(__name__)

SET_ICON_DIRECTORY = Path("icon/set")
SET_LIST_URL = "https://api.pokemontcg.io/v2/sets"
SET_API_KEY_ENV = "POKEMON_TCG_API_KEY"


def _build_retrying_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.setdefault("User-Agent", "kartoteka/1.0")
    api_key = os.getenv(SET_API_KEY_ENV, "").strip()
    if api_key:
        session.headers.setdefault("X-Api-Key", api_key)
    return session


def _extract_clean_code(set_payload: dict[str, object]) -> Optional[str]:
    raw_candidates: Iterable[Optional[str]] = (
        set_payload.get("code"),
        set_payload.get("setCode"),
        set_payload.get("ptcgoCode"),
        set_payload.get("slug"),
        set_payload.get("id"),
        set_payload.get("name"),
    )
    for candidate in raw_candidates:
        if not isinstance(candidate, str):
            continue
        cleaned = set_utils.clean_code(candidate)
        if cleaned:
            return cleaned
    return None


def _extract_symbol_url(set_payload: dict[str, object]) -> Optional[str]:
    images = set_payload.get("images")
    if isinstance(images, dict):
        symbol = images.get("symbol")
        if isinstance(symbol, str) and symbol.strip():
            return symbol.strip()
    return None


def _fetch_set_payloads(
    *, session: requests.Session, timeout: float = 10.0
) -> list[dict[str, object]]:
    try:
        response: Response = session.get(SET_LIST_URL, timeout=timeout)
    except requests.Timeout:
        logger.warning("Timed out while fetching Pokémon set definitions")
        return []
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logger.warning("Failed to fetch Pokémon set definitions: %s", exc)
        return []

    if response.status_code != 200:
        logger.warning(
            "Pokémon TCG API returned status %s while fetching sets", response.status_code
        )
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.warning("Pokémon TCG API returned invalid JSON for set list")
        return []

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        logger.warning("Pokémon TCG API payload lacked a set list")
        return []

    sets: list[dict[str, object]] = []
    for item in data:
        if isinstance(item, dict):
            sets.append(item)
    return sets


def ensure_set_icons(
    *,
    force: bool = False,
    icons_directory: Path | str = SET_ICON_DIRECTORY,
    session: requests.Session | None = None,
    timeout: float = 10.0,
) -> list[Path]:
    """Ensure the Pokémon set icon cache is populated locally."""

    target_directory = Path(icons_directory)
    try:
        target_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem errors
        logger.warning("Unable to create icon directory %s: %s", target_directory, exc)
        return []

    created_session = session is None
    http = session or _build_retrying_session()
    try:
        saved_paths: list[Path] = []
        for set_payload in _fetch_set_payloads(session=http, timeout=timeout):
            clean_code = _extract_clean_code(set_payload)
            if not clean_code:
                continue
            symbol_url = _extract_symbol_url(set_payload)
            if not symbol_url:
                continue
            destination = target_directory / f"{clean_code}.png"
            if destination.exists() and not force:
                continue

            try:
                response = http.get(symbol_url, timeout=timeout)
            except requests.Timeout:
                logger.warning("Timeout while downloading symbol for set %s", clean_code)
                continue
            except requests.RequestException as exc:  # pragma: no cover - network errors
                logger.warning("Failed to download symbol for set %s: %s", clean_code, exc)
                continue

            if response.status_code != 200:
                logger.warning(
                    "Pokémon TCG API returned status %s for symbol %s",
                    response.status_code,
                    clean_code,
                )
                continue

            try:
                destination.write_bytes(response.content)
            except OSError as exc:  # pragma: no cover - filesystem errors
                logger.warning("Failed to save symbol for set %s: %s", clean_code, exc)
                continue

            saved_paths.append(destination)

        return saved_paths
    finally:
        if created_session:
            http.close()


__all__ = ["ensure_set_icons"]

