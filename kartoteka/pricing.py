"""Utilities for card price retrieval shared between the UI and web API."""

from __future__ import annotations

import logging
import os
import unicodedata
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)

# Default configuration mirrors the desktop application so that both the UI and
# web API share the same behaviour without duplicating constants.
PRICE_MULTIPLIER = float(os.getenv("PRICE_MULTIPLIER", "1.23"))
HOLO_REVERSE_MULTIPLIER = float(os.getenv("HOLO_REVERSE_MULTIPLIER", "3.5"))
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
DEFAULT_EXCHANGE_RATE = float(os.getenv("DEFAULT_EUR_PLN", "4.265"))


def sanitize_number(value: str) -> str:
    """Return ``value`` without leading zeros.

    An empty input returns an empty string instead of ``"0"`` so callers can
    decide how to handle missing numbers explicitly.
    """

    text = (value or "").strip()
    if not text:
        return ""
    return text.lstrip("0") or "0"


def normalize(text: str, keep_spaces: bool = False) -> str:
    """Normalise ``text`` for API queries and lookups."""

    if not text:
        return ""
    value = unicodedata.normalize("NFKD", text)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    for suffix in (" shiny", " promo"):
        value = value.replace(suffix, "")
    value = value.replace("-", "")
    if not keep_spaces:
        value = value.replace(" ", "")
    return value.strip()


def extract_cardmarket_price(card: dict | None) -> Optional[float]:
    """Return the most representative price from TCG data."""

    prices = (card or {}).get("prices") or {}
    cardmarket = prices.get("cardmarket") or {}

    def _float_value(key: str) -> float:
        try:
            return float(cardmarket.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    avg_30d = _float_value("30d_average")
    trend = _float_value("trendPrice") or _float_value("trend_price")
    values = [value for value in (avg_30d, trend) if value > 0]
    if len(values) == 2:
        return sum(values) / 2
    if len(values) == 1:
        return values[0]

    lowest = _float_value("lowest_near_mint")
    if lowest > 0:
        return lowest
    return None


def get_exchange_rate(session: Optional[requests.sessions.Session] = None) -> float:
    """Fetch the EUR/PLN exchange rate using the public NBP API."""

    http = session or requests
    try:
        response = http.get(
            "https://api.nbp.pl/api/exchangerates/rates/A/EUR/?format=json",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            return float(data["rates"][0]["mid"])
    except requests.Timeout:
        logger.warning("Exchange rate request timed out")
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Failed to fetch exchange rate: %s", exc)
    return DEFAULT_EXCHANGE_RATE


def _split_number_total(value: str) -> tuple[str, Optional[str]]:
    """Return the number part and optional total from ``value``."""

    text = (value or "").strip()
    if not text:
        return "", None
    if "/" in text:
        number, total = text.split("/", 1)
        return number.strip(), total.strip() or None
    return text, None


def _card_sort_key(card: dict[str, Any]) -> tuple[int, str]:
    """Return a sort key that keeps numeric identifiers ordered."""

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


def _build_card_payload(card: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return a normalised representation of a card payload."""

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
    card_number_clean = sanitize_number(card_number_part.lower())
    if not card_number_clean:
        return None
    card_total_clean = sanitize_number(card_total_from_number or raw_total)

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
    artist = card.get("artist") or card.get("illustrator")
    series = (
        episode.get("series")
        or episode.get("era")
        or card.get("series")
    )
    release_date = (
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


def fetch_card_price(
    name: str,
    number: str,
    set_name: str,
    *,
    set_code: Optional[str] = None,
    is_reverse: bool = False,
    is_holo: bool = False,
    price_multiplier: float | None = None,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    get_rate: Optional[Callable[[], float]] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> Optional[float]:
    """Return the current PLN price for a card.

    The function mirrors the behaviour of :class:`kartoteka.ui.CardEditorApp`
    while remaining independent from Tkinter specifics.  It uses the
    TCGGO/RapidAPI endpoint and converts the result to PLN using the provided
    exchange rate callback.
    """

    if price_multiplier is None:
        price_multiplier = PRICE_MULTIPLIER
    rapidapi_key = rapidapi_key if rapidapi_key is not None else RAPIDAPI_KEY
    rapidapi_host = rapidapi_host if rapidapi_host is not None else RAPIDAPI_HOST
    http = session or requests

    name_api = normalize(name, keep_spaces=True)
    name_input = normalize(name)
    number_part, _ = _split_number_total(str(number).lower())
    number_input = sanitize_number(number_part.lower()) if number_part else ""
    set_input = (set_name or "").strip().lower()
    set_code = (set_code or set_name or "").strip().lower()

    try:
        headers: dict[str, str] = {}
        if rapidapi_key and rapidapi_host:
            url = f"https://{rapidapi_host}/cards/search"
            params = {"search": name_api}
            headers = {
                "X-RapidAPI-Key": rapidapi_key,
                "X-RapidAPI-Host": rapidapi_host,
            }
        else:
            url = "https://www.tcggo.com/api/cards/"
            params = {
                "name": name_api,
                "number": number_input,
                "set": set_code,
            }

        response = http.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code != 200:
            logger.warning("API error: %s", response.status_code)
            return None

        cards = response.json()
        if isinstance(cards, dict):
            if "cards" in cards:
                cards = cards["cards"]
            elif "data" in cards:
                cards = cards["data"]
            else:
                cards = []

        candidates = []
        for card in cards:
            card_name = normalize(card.get("name", ""))
            card_number_raw = str(card.get("card_number", "")).lower()
            card_number = sanitize_number(card_number_raw.split("/", 1)[0])
            episode = card.get("episode") or {}
            card_set = str(episode.get("name", "")).lower()

            name_match = name_input in card_name
            number_match = number_input == card_number if number_input else True
            set_match = not set_input or set_input in card_set or card_set.startswith(set_input)

            if name_match and number_match and set_match:
                candidates.append(card)

        if candidates:
            best = candidates[0]
            price_eur = extract_cardmarket_price(best)
            if price_eur is not None:
                rate_func = get_rate or get_exchange_rate
                eur_pln = rate_func()
                price_pln = round(float(price_eur) * eur_pln * price_multiplier, 2)
                logger.info(
                    "Cena %s (%s, %s) = %s PLN",
                    best.get("name"),
                    number_input,
                    set_input,
                    price_pln,
                )
                return price_pln

        logger.debug("Nie znaleziono dokładnej karty. Zbliżone:")
        for card in cards:
            episode = card.get("episode") or {}
            card_number = str(card.get("card_number", "")).lower()
            card_set = str(episode.get("name", "")).lower()
            if (not number_input or number_input == card_number) and (
                not set_input or set_input in card_set
            ):
                logger.debug(
                    "%s | %s | %s",
                    card.get("name"),
                    card_number,
                    episode.get("name"),
                )

    except requests.Timeout:
        logger.warning("Request timed out")
    except requests.RequestException as exc:
        logger.warning("Fetching price from TCGGO failed: %s", exc)
    except ValueError as exc:
        logger.warning("Invalid JSON from TCGGO: %s", exc)

    return None


def search_cards(
    name: str,
    number: str,
    *,
    set_name: Optional[str] = None,
    total: Optional[str] = None,
    limit: int = 10,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> list[dict]:
    """Return card suggestions from the TCGGO API.

    The returned dictionaries contain enough data to populate the collection
    form without persisting any information yet.
    """

    if not name or not number:
        return []

    http = session or requests
    rapidapi_key = rapidapi_key if rapidapi_key is not None else RAPIDAPI_KEY
    rapidapi_host = rapidapi_host if rapidapi_host is not None else RAPIDAPI_HOST

    number_part, number_total = _split_number_total(str(number))
    if total:
        _, forced_total = _split_number_total(str(total))
        number_total = forced_total or number_total
    number_clean = sanitize_number(number_part)
    total_clean = sanitize_number(number_total) if number_total else ""

    name_api = normalize(name, keep_spaces=True)
    params: dict[str, str] = {}
    headers: dict[str, str] = {}
    url = "https://www.tcggo.com/api/cards/"

    if rapidapi_key and rapidapi_host:
        url = f"https://{rapidapi_host}/cards/search"
        params = {"search": name_api}
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host,
        }
    else:
        params = {"name": name_api}
        if number_clean:
            params["number"] = number_clean
        if total_clean:
            params["total"] = total_clean
        if set_name:
            params["set"] = normalize(set_name, keep_spaces=True)

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
        logger.warning("Fetching cards from TCGGO failed: %s", exc)
        return []

    if isinstance(cards, dict):
        cards = cards.get("cards") or cards.get("data") or []

    name_norm = normalize(name)
    total_norm = total_clean
    set_norm = normalize(set_name) if set_name else ""

    suggestions: list[dict[str, Any]] = []
    for card in cards or []:
        payload = _build_card_payload(card)
        if not payload:
            continue

        card_name_norm = normalize(payload.get("name", ""))
        card_number_clean = payload.get("number") or ""
        total_value = payload.get("total") or ""
        card_total_clean = sanitize_number(str(total_value)) if total_value else ""

        if number_clean and card_number_clean != number_clean:
            continue
        if total_clean and card_total_clean and card_total_clean != total_clean:
            continue

        card_set_norm = normalize(payload.get("set_name"))
        score = 0
        if name_norm and card_name_norm == name_norm:
            score += 3
        elif name_norm and name_norm in card_name_norm:
            score += 1
        if number_clean and card_number_clean == number_clean:
            score += 3
        if total_norm and card_total_clean == total_norm:
            score += 1
        if set_norm and set_norm in card_set_norm:
            score += 1

        if not payload.get("name"):
            payload["name"] = name
        if not payload.get("image_small") and payload.get("image_large"):
            payload["image_small"] = payload.get("image_large")
        payload["_score"] = score
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
        key = (item.get("set_code"), item.get("number"))
        if key in seen:
            continue
        seen.add(key)
        item.pop("_score", None)
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
) -> list[dict[str, Any]]:
    """Return a selection of cards belonging to ``set_code``."""

    if not set_code:
        return []

    http = session or requests
    rapidapi_key = rapidapi_key if rapidapi_key is not None else RAPIDAPI_KEY
    rapidapi_host = rapidapi_host if rapidapi_host is not None else RAPIDAPI_HOST

    params: dict[str, str] = {}
    headers: dict[str, str] = {}
    url = "https://www.tcggo.com/api/cards/"
    if rapidapi_key and rapidapi_host:
        url = f"https://{rapidapi_host}/cards/search"
        params = {"set": set_code}
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host,
        }
    else:
        params = {"set": set_code}

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
        logger.warning("Fetching cards for set %s failed: %s", set_code, exc)
        return []

    if isinstance(cards, dict):
        cards = cards.get("cards") or cards.get("data") or cards.get("results") or []

    results: list[dict[str, Any]] = []
    for card in cards or []:
        payload = _build_card_payload(card)
        if not payload:
            continue
        if not payload.get("name"):
            payload["name"] = card.get("name") or ""
        if not payload.get("image_small") and payload.get("image_large"):
            payload["image_small"] = payload.get("image_large")
        results.append(payload)

    results.sort(key=_card_sort_key)
    if limit and limit > 0:
        return results[:limit]
    return results

