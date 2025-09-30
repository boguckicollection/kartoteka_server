"""Minimal Pokémon TCG API helpers for catalogue operations."""

from __future__ import annotations

import logging
import os
from difflib import SequenceMatcher
from typing import Any, Optional

import requests

from ..utils import text

logger = logging.getLogger(__name__)

POKEMONTCG_API_URL = os.getenv("POKEMONTCG_API_URL", "https://api.pokemontcg.io/v2/cards")
POKEMONTCG_API_KEY = os.getenv("POKEMONTCG_API_KEY")


def _apply_default_user_agent(
    headers: dict[str, str],
    session: Optional[requests.sessions.Session],
) -> None:
    session_headers = getattr(session, "headers", None) or {}
    user_agent = session_headers.get("User-Agent") if session_headers else None
    if user_agent:
        headers.setdefault("User-Agent", str(user_agent))
    else:
        headers.setdefault("User-Agent", "kartoteka/1.0")


def _split_number_total(value: str) -> tuple[str, Optional[str]]:
    text_value = (value or "").strip()
    if not text_value:
        return "", None
    if "/" in text_value:
        number, total = text_value.split("/", 1)
        return number.strip(), total.strip() or None
    return text_value, None


def _card_sort_key(card: dict[str, Any]) -> tuple[int, str]:
    number = str(card.get("number") or "")
    try:
        return (0, f"{int(number):04d}")
    except ValueError:
        return (1, number)


def _extract_images(card: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    images = card.get("images") or {}
    image_small = None
    image_large = None
    if isinstance(images, dict):
        image_small = (
            images.get("small")
            or images.get("smallUrl")
            or images.get("thumbnail")
            or images.get("thumb")
            or images.get("icon")
        )
        image_large = (
            images.get("large")
            or images.get("largeUrl")
            or images.get("hires")
            or images.get("image")
            or images.get("full")
        )
    if not image_small:
        image_small = (
            card.get("image")
            or card.get("imageUrl")
            or card.get("image_url")
            or card.get("thumbnail")
        )
    if not image_large:
        image_large = (
            card.get("imageUrlHiRes")
            or card.get("hires")
            or card.get("image_large")
            or image_small
        )
    if image_small and isinstance(image_small, dict):
        image_small = image_small.get("url")
    if image_large and isinstance(image_large, dict):
        image_large = image_large.get("url")
    return image_small, image_large


def _normalize_text_field(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("name", "value", "label", "title", "text"):
            if key in value:
                normalized = _normalize_text_field(value.get(key))
                if normalized:
                    return normalized
        for nested in value.values():
            normalized = _normalize_text_field(nested)
            if normalized:
                return normalized
        return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_text_field(item)
            if normalized:
                return normalized
        return None
    return str(value)


def build_card_payload(card: dict[str, Any]) -> Optional[dict[str, Any]]:
    episode = card.get("episode") or card.get("set") or {}
    set_name_value = (
        episode.get("name")
        or card.get("set_name")
        or card.get("setName")
        or ""
    )
    set_code_value = (
        episode.get("code")
        or episode.get("slug")
        or episode.get("id")
        or card.get("set_code")
        or card.get("setCode")
    )

    raw_number = str(
        card.get("card_number")
        or card.get("number")
        or card.get("collector_number")
        or ""
    )
    raw_total = str(
        card.get("total_prints")
        or card.get("total")
        or card.get("set_total")
        or ""
    )

    card_number_part, card_total_from_number = _split_number_total(raw_number)
    card_number_clean = text.sanitize_number(card_number_part.lower())
    if not card_number_clean:
        return None
    card_total_clean = text.sanitize_number(card_total_from_number or raw_total)

    number_display = (
        card.get("card_number_display")
        or card.get("printed_number")
        or raw_number
    )
    if not number_display:
        number_display = (
            f"{card_number_clean}/{card_total_clean}"
            if card_total_clean
            else card_number_clean
        )

    rarity = (
        card.get("rarity")
        or card.get("rarity_name")
        or card.get("rarityName")
        or None
    )
    artist = _normalize_text_field(card.get("artist") or card.get("illustrator"))
    series = _normalize_text_field(
        episode.get("series")
        or episode.get("era")
        or card.get("series")
    )
    release_date = _normalize_text_field(
        episode.get("releaseDate")
        or episode.get("release_date")
        or card.get("releaseDate")
        or card.get("release_date")
    )
    set_icon = (
        episode.get("symbol")
        or episode.get("logo")
        or episode.get("icon")
        or card.get("set_symbol")
        or card.get("set_logo")
    )

    image_small, image_large = _extract_images(card)

    return {
        "name": card.get("name") or "",
        "number": card_number_clean,
        "number_display": number_display,
        "total": card_total_clean or None,
        "set_name": set_name_value,
        "set_code": set_code_value,
        "rarity": rarity,
        "image_small": image_small,
        "image_large": image_large,
        "artist": artist,
        "series": series,
        "release_date": release_date,
        "set_icon": set_icon,
    }


def search_cards(
    *,
    name: str,
    number: str | None = None,
    set_name: Optional[str] = None,
    total: Optional[str] = None,
    limit: int = 10,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> list[dict]:
    if not name:
        return []

    http = session or requests

    number_part = ""
    number_total = ""
    if number:
        number_part, number_total = _split_number_total(str(number))
    if total:
        _, forced_total = _split_number_total(str(total))
        number_total = forced_total or number_total
    number_clean = text.sanitize_number(number_part) if number_part else ""
    total_clean = text.sanitize_number(number_total) if number_total else ""

    name_api = text.normalize(name, keep_spaces=True)
    api_key = rapidapi_key if rapidapi_key is not None else POKEMONTCG_API_KEY
    url = POKEMONTCG_API_URL
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    if api_key:
        headers["X-Api-Key"] = api_key

    def _escape_query(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', r"\"")

    query_parts: list[str] = []
    if name_api:
        query_parts.append(f'name:"*{_escape_query(name_api)}*"')
    if number_clean:
        query_parts.append(f'number:"{_escape_query(number_clean)}"')
    if set_name:
        set_query = text.normalize(set_name, keep_spaces=True)
        if set_query:
            escaped = _escape_query(set_query)
            query_parts.append(
                "(" +
                " OR ".join(
                    (
                        f'set.id:"{escaped}"',
                        f'set.ptcgoCode:"{escaped}"',
                        f'set.name:"*{escaped}*"',
                    )
                ) +
                ")"
            )
    if total_clean:
        escaped_total = _escape_query(total_clean)
        query_parts.append(
            f"(set.total:{escaped_total} OR set.printedTotal:{escaped_total})"
        )

    if not query_parts:
        return []

    page_size = max(limit * 5, 50)
    page_size = min(page_size, 250)
    params = {
        "q": " and ".join(query_parts),
        "page": "1",
        "pageSize": str(page_size),
    }

    try:
        response = http.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code != 200:
            logger.warning("API error: %s", response.status_code)
            return []
        cards = response.json()
    except requests.Timeout:
        logger.warning("Request timed out")
        return []
    except (requests.RequestException, ValueError) as exc:  # pragma: no cover
        logger.warning("Fetching cards from the Pokémon TCG API failed: %s", exc)
        return []

    if isinstance(cards, dict):
        cards = cards.get("data") or cards.get("cards") or []

    name_norm = text.normalize(name)
    total_norm = total_clean
    set_norm = text.normalize(set_name) if set_name else ""

    suggestions: list[dict[str, Any]] = []
    threshold = text.SEARCH_SCORE_THRESHOLD
    threshold_points = threshold / 20 if threshold else 0
    for card in cards or []:
        payload = build_card_payload(card)
        if not payload:
            continue

        card_name_norm = text.normalize(payload.get("name", ""))
        card_number_clean = payload.get("number") or ""
        total_value = payload.get("total") or ""
        card_total_clean = text.sanitize_number(str(total_value)) if total_value else ""

        name_similarity = 0.0
        if name_norm and card_name_norm:
            if card_name_norm == name_norm:
                name_similarity = 1.0
            else:
                name_similarity = SequenceMatcher(None, name_norm, card_name_norm).ratio()

        if number_clean and card_number_clean != number_clean:
            continue
        if total_clean and card_total_clean and card_total_clean != total_clean:
            continue

        card_set_norm = text.normalize(payload.get("set_name"))
        score = 0
        if name_norm and card_name_norm == name_norm:
            score += 3
        elif name_norm and name_norm in card_name_norm:
            score += 1
        if number_clean and card_number_clean == number_clean:
            score += 3
        elif not number_clean and card_number_clean:
            score += 1
        if total_norm and card_total_clean == total_norm:
            score += 1
        if set_norm and set_norm in card_set_norm:
            score += 1

        if not payload.get("name"):
            payload["name"] = name
        if not payload.get("image_small") and payload.get("image_large"):
            payload["image_small"] = payload.get("image_large")
        payload["_score"] = score
        payload["_score_value"] = score * 20
        payload["_name_similarity"] = name_similarity
        suggestions.append(payload)

    suggestions.sort(
        key=lambda item: (
            item.get("_score", 0),
            item.get("set_name") or "",
            item.get("number_display") or "",
        ),
        reverse=True,
    )

    seen: set[tuple[str | None, str]] = set()
    results: list[dict] = []
    for item in suggestions:
        score_value = float(item.get("_score", 0) or 0)
        if score_value <= 0:
            continue
        if threshold_points and score_value < threshold_points:
            similarity = float(item.get("_name_similarity") or 0)
            if similarity < text.NAME_SIMILARITY_THRESHOLD:
                continue
        key = (item.get("set_code"), item.get("number"))
        if key in seen:
            continue
        seen.add(key)
        item.pop("_score", None)
        item.pop("_score_value", None)
        item.pop("_name_similarity", None)
        if not item.get("image_small") and item.get("image_large"):
            item["image_small"] = item["image_large"]
        results.append(item)
        if len(results) >= limit:
            break

    return results


def list_set_cards(
    set_code: str,
    *,
    limit: int = 12,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> tuple[list[dict[str, Any]], int]:
    if not set_code:
        return [], 0

    http = session or requests
    api_key = rapidapi_key if rapidapi_key is not None else POKEMONTCG_API_KEY
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    if api_key:
        headers["X-Api-Key"] = api_key

    def _escape_query(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', r"\"")

    set_value = set_code.strip()
    normalized = text.normalize(set_code, keep_spaces=True)
    escaped_value = _escape_query(set_value)
    set_filters = {
        f'set.id:"{escaped_value}"',
        f'set.ptcgoCode:"{escaped_value}"',
        f'set.name:"*{escaped_value}*"',
    }
    if normalized and normalized != set_value:
        escaped_normalized = _escape_query(normalized)
        set_filters.add(f'set.id:"{escaped_normalized}"')
        set_filters.add(f'set.ptcgoCode:"{escaped_normalized}"')
        set_filters.add(f'set.name:"*{escaped_normalized}*"')

    query = "(" + " OR ".join(sorted(set_filters)) + ")"
    page = 1
    page_size = 250
    results: list[dict[str, Any]] = []
    fetched_total = 0
    request_count = 0

    while True:
        params = {
            "q": query,
            "page": str(page),
            "pageSize": str(page_size),
        }
        try:
            response = http.get(
                POKEMONTCG_API_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )
        except requests.Timeout:
            request_count += 1
            logger.warning("Request timed out")
            break
        except (requests.RequestException, ValueError) as exc:  # pragma: no cover
            request_count += 1
            logger.warning("Fetching cards for set %s failed: %s", set_code, exc)
            break
        else:
            request_count += 1
            if response.status_code != 200:
                logger.warning("API error: %s", response.status_code)
                break
            payload = response.json()

        cards = []
        total_count = 0
        if isinstance(payload, dict):
            cards = payload.get("data") or []
            total_count = int(payload.get("totalCount") or 0)
        elif isinstance(payload, list):
            cards = payload

        if not cards:
            break

        for card in cards:
            item = build_card_payload(card)
            if not item:
                continue
            if not item.get("name"):
                item["name"] = card.get("name") or ""
            if not item.get("image_small") and item.get("image_large"):
                item["image_small"] = item.get("image_large")
            results.append(item)

        fetched_total += len(cards)
        if limit and limit > 0 and len(results) >= limit:
            break

        if total_count:
            if fetched_total >= total_count:
                break
        elif len(cards) < page_size:
            break

        page += 1

    results.sort(key=_card_sort_key)
    if limit and limit > 0:
        results = results[:limit]
    return results, request_count
