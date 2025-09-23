"""Utilities for card price retrieval shared between the UI and web API."""

from __future__ import annotations

import logging
import os
import unicodedata
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

# Default configuration mirrors the desktop application so that both the UI and
# web API share the same behaviour without duplicating constants.
PRICE_MULTIPLIER = float(os.getenv("PRICE_MULTIPLIER", "1.23"))
HOLO_REVERSE_MULTIPLIER = float(os.getenv("HOLO_REVERSE_MULTIPLIER", "3.5"))
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
DEFAULT_EXCHANGE_RATE = float(os.getenv("DEFAULT_EUR_PLN", "4.265"))


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
    number_input = (number or "").strip().lower()
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
            card_number = str(card.get("card_number", "")).lower()
            episode = card.get("episode") or {}
            card_set = str(episode.get("name", "")).lower()

            name_match = name_input in card_name
            number_match = number_input == card_number
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
            if number_input == card_number and (not set_input or set_input in card_set):
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

