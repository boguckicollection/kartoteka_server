"""Minimal RapidAPI Pokémon TCG helpers for catalogue operations."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from ..utils import text, sets as set_utils

# Cache for set code to API mapping
_SET_CODE_TO_API_CACHE: dict[str, dict[str, Any]] = {}


def _load_set_code_mapping() -> dict[str, dict[str, Any]]:
    """Load set code to API ID mapping from JSON file."""
    global _SET_CODE_TO_API_CACHE
    if _SET_CODE_TO_API_CACHE:
        return _SET_CODE_TO_API_CACHE
    
    # Try to find the mapping file
    mapping_paths = [
        Path(__file__).parent.parent.parent.parent / "set_code_to_api.json",
        Path(os.getcwd()) / "set_code_to_api.json",
        Path(__file__).parent / "set_code_to_api.json",
    ]
    
    for path in mapping_paths:
        if path.exists():
            try:
                with open(path) as f:
                    _SET_CODE_TO_API_CACHE = json.load(f)
                    logger.info("Loaded set mapping from %s (%d sets)", path, len(_SET_CODE_TO_API_CACHE))
                    return _SET_CODE_TO_API_CACHE
            except Exception as e:
                logger.warning("Failed to load set mapping from %s: %s", path, e)
    
    logger.warning("Set code mapping file not found, API sync will use fallback")
    return {}

logger = logging.getLogger(__name__)

RAPIDAPI_DEFAULT_HOST = "pokemon-tcg-api.p.rapidapi.com"
_EUR_PLN_RATE_CACHE: dict[str, float | None] = {"value": None, "expires": 0.0}
_EUR_PLN_RATE_TTL = 60 * 60  # 1 hour

_RARITY_ICON_BASE_PATH = "/static/icons/rarity"
_RARITY_ICON_IMAGE_BASE_PATH = "/icon/rarity"
_RARITY_ICON_VECTOR_MAP = {
    "common": f"{_RARITY_ICON_BASE_PATH}/common.svg",
    "uncommon": f"{_RARITY_ICON_BASE_PATH}/uncommon.svg",
    "rare": f"{_RARITY_ICON_BASE_PATH}/rare.svg",
    "rare-holo": f"{_RARITY_ICON_BASE_PATH}/rare-holo.svg",
    "holo-rare": f"{_RARITY_ICON_BASE_PATH}/rare-holo.svg",
    "double-rare": f"{_RARITY_ICON_BASE_PATH}/rare-ultra.svg",
    "rare-double": f"{_RARITY_ICON_BASE_PATH}/rare-ultra.svg",
    "ultra-rare": f"{_RARITY_ICON_BASE_PATH}/rare-ultra.svg",
    "rare-ultra": f"{_RARITY_ICON_BASE_PATH}/rare-ultra.svg",
    "hyper-rare": f"{_RARITY_ICON_BASE_PATH}/rare-secret.svg",
    "rare-secret": f"{_RARITY_ICON_BASE_PATH}/rare-secret.svg",
    "secret-rare": f"{_RARITY_ICON_BASE_PATH}/rare-secret.svg",
    "rare-rainbow": f"{_RARITY_ICON_BASE_PATH}/rare-rainbow.svg",
    "rainbow-rare": f"{_RARITY_ICON_BASE_PATH}/rare-rainbow.svg",
    "illustration-rare": f"{_RARITY_ICON_BASE_PATH}/rare-illustration.svg",
    "rare-illustration": f"{_RARITY_ICON_BASE_PATH}/rare-illustration.svg",
    "special-illustration-rare": f"{_RARITY_ICON_BASE_PATH}/rare-illustration.svg",
    "rare-special-illustration": f"{_RARITY_ICON_BASE_PATH}/rare-illustration.svg",
    "shiny-rare": f"{_RARITY_ICON_BASE_PATH}/rare-shiny.svg",
    "rare-shiny": f"{_RARITY_ICON_BASE_PATH}/rare-shiny.svg",
    "shinyrare": f"{_RARITY_ICON_BASE_PATH}/rare-shiny.svg",
    "ace-spec": f"{_RARITY_ICON_BASE_PATH}/rare-ace.svg",
    "rare-ace": f"{_RARITY_ICON_BASE_PATH}/rare-ace.svg",
    "ace-spec-rare": f"{_RARITY_ICON_BASE_PATH}/rare-ace.svg",
    "promo": f"{_RARITY_ICON_BASE_PATH}/promo.svg",
}
_RARITY_ICON_MAP = {
    "common": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Common.png",
    "uncommon": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Uncommon.png",
    "rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png",
    "rare-holo": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png",
    "holo-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png",
    "double-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png",
    "rare-double": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png",
    "ultra-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png",
    "rare-ultra": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png",
    "hyper-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png",
    "rare-secret": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png",
    "secret-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png",
    "rare-rainbow": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png",
    "rainbow-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png",
    "illustration-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Illustration%20Rare.png",
    "rare-illustration": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Illustration%20Rare.png",
    "special-illustration-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Special_Illustration_Rare.png",
    "rare-special-illustration": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Special_Illustration_Rare.png",
    "shiny-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Shiny_Rare.png",
    "rare-shiny": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Shiny_Rare.png",
    "shinyrare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ShinyRare.png",
    "ace-spec": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png",
    "rare-ace": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png",
    "ace-spec-rare": f"{_RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png",
}
_RARITY_ICON_RULES = (
    (re.compile(r"ace[\s-]?spec", re.IGNORECASE), "ace-spec"),
    (re.compile(r"special\s+illustration", re.IGNORECASE), "special-illustration-rare"),
    (re.compile(r"illustration", re.IGNORECASE), "illustration-rare"),
    (re.compile(r"(hyper|secret|rainbow|gold)", re.IGNORECASE), "hyper-rare"),
    (re.compile(r"(shiny|shining|radiant)", re.IGNORECASE), "shiny-rare"),
    (re.compile(r"double", re.IGNORECASE), "double-rare"),
    (
        re.compile(
            r"(ultra|vmax|v-star|vstar|v-union|gx|ex|mega|prime|legend)",
            re.IGNORECASE,
        ),
        "ultra-rare",
    ),
    (re.compile(r"holo", re.IGNORECASE), "rare"),
    (re.compile(r"rare", re.IGNORECASE), "rare"),
    (re.compile(r"uncommon", re.IGNORECASE), "uncommon"),
    (re.compile(r"common", re.IGNORECASE), "common"),
)

_SEVEN_DAY_AVERAGE_KEYS: tuple[str, ...] = (
    "7d_average",
    "avg7",
    "avg_7",
    "sevenDayAverage",
    "seven_day_average",
    "sevenDayAvg",
)

_PRICE_HISTORY_KEYS: tuple[str, ...] = (
    "marketPrice",
    "market_price",
    "market",
    "price",
    "averageSellPrice",
    "avgSellPrice",
    "avg",
    "avg7",
    "avg30",
    "trend",
    "trendPrice",
    "lowPrice",
    "low",
    "highPrice",
    "high",
    "median",
    "value",
    "directLow",
    "directHigh",
)


def _normalize_rarity_key(value: str) -> str:
    text_value = value.lower().strip()
    text_value = re.sub(r"[^a-z0-9]+", "-", text_value)
    text_value = text_value.strip("-")
    return text_value


def resolve_rarity_icon_path(rarity: Optional[str]) -> Optional[str]:
    """Return a local rarity icon path that mirrors the frontend resolver."""

    if not rarity:
        return None
    normalized = _normalize_rarity_key(str(rarity))
    if normalized:
        vector_icon = _RARITY_ICON_VECTOR_MAP.get(normalized)
        if vector_icon:
            return vector_icon
        mapped = _RARITY_ICON_MAP.get(normalized)
        if mapped:
            return mapped
    lower_value = str(rarity).lower()
    for pattern, key in _RARITY_ICON_RULES:
        if pattern.search(lower_value):
            vector_icon = _RARITY_ICON_VECTOR_MAP.get(key)
            if vector_icon:
                return vector_icon
            return _RARITY_ICON_MAP.get(key)
    return None


def get_eur_pln_rate(
    session: Optional[requests.sessions.Session] = None,
) -> Optional[float]:
    """Return the EUR→PLN exchange rate using a simple in-memory cache."""

    now = time.time()
    cached_value = _EUR_PLN_RATE_CACHE.get("value")
    expires_at = _EUR_PLN_RATE_CACHE.get("expires", 0.0)
    if cached_value is not None and now < expires_at:
        return cached_value

    http = session or requests
    url = "https://api.nbp.pl/api/exchangerates/rates/A/EUR"

    try:
        response = http.get(url, params={"format": "json"}, timeout=5.0)
    except requests.Timeout:
        logger.warning("Request for EUR/PLN rate timed out")
        return cached_value
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logger.warning("Fetching EUR/PLN rate failed: %s", exc)
        return cached_value

    if response.status_code != 200:
        logger.warning("NBP API error: %s", response.status_code)
        return cached_value

    try:
        payload = response.json()
    except ValueError:
        logger.warning("NBP API returned invalid JSON")
        return cached_value

    rates = payload.get("rates") if isinstance(payload, dict) else None
    rate_value: Optional[float] = None
    if isinstance(rates, list) and rates:
        first_rate = rates[0] or {}
        if isinstance(first_rate, dict):
            for key in ("mid", "ask", "bid"):
                rate_value = _normalize_price_value(first_rate.get(key))
                if rate_value is not None:
                    break

    if rate_value is None:
        logger.warning("NBP API payload did not contain a usable EUR/PLN rate")
        return cached_value

    _EUR_PLN_RATE_CACHE["value"] = rate_value
    _EUR_PLN_RATE_CACHE["expires"] = now + _EUR_PLN_RATE_TTL
    return rate_value


def _normalize_host(rapidapi_host: Optional[str]) -> tuple[str, str]:
    host_value = rapidapi_host or RAPIDAPI_DEFAULT_HOST
    if "://" not in host_value:
        return host_value, host_value
    parsed = urlparse(host_value)
    netloc = parsed.netloc or parsed.path
    return host_value, netloc or host_value


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


def _normalize_price_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        price = float(value)
    elif isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        text_value = text_value.replace(",", ".")
        try:
            price = float(text_value)
        except ValueError:
            return None
    else:
        return None
    if price != price or price in (float("inf"), float("-inf")) or price < 0:
        return None
    return round(price, 2)


def _extract_cardmarket_price(card: dict[str, Any]) -> Optional[float]:
    # For products, cardmarket data is in card.prices.cardmarket
    # For cards, it's directly in card.cardmarket
    prices = card.get("prices") or {}
    cardmarket = (
        card.get("cardmarket")
        or card.get("cardMarket")
        or card.get("card_market")
        or (prices.get("cardmarket") if isinstance(prices, dict) else None)
        or (prices.get("cardMarket") if isinstance(prices, dict) else None)
        or {}
    )
    if not isinstance(cardmarket, dict):
        return None
    prices = cardmarket.get("prices")
    if isinstance(prices, dict):
        for key in (
            "averageSellPrice",
            "trendPrice",
            "avg7",
            "avg30",
            "avg1",
            "lowPrice",
        ):
            price = _normalize_price_value(prices.get(key))
            if price is not None:
                return price
    # Check direct price fields including 'lowest' (common in product data)
    # Use only international/English prices (without regional variants like _DE, _FR)
    for key in ("price", "marketPrice", "lowest", "lowest_near_mint"):
        price = _normalize_price_value(cardmarket.get(key))
        if price is not None:
            return price
    return None


def _extract_tcgplayer_price(card: dict[str, Any]) -> Optional[float]:
    tcgplayer = card.get("tcgplayer") or card.get("tcgPlayer") or {}
    if not isinstance(tcgplayer, dict):
        return None
    prices = tcgplayer.get("prices")
    if isinstance(prices, dict):
        for variant in prices.values():
            if not isinstance(variant, dict):
                continue
            for key in ("market", "mid", "directLow", "low", "high"):
                price = _normalize_price_value(variant.get(key))
                if price is not None:
                    return price
    for key in ("market", "mid", "price"):
        price = _normalize_price_value(tcgplayer.get(key))
        if price is not None:
            return price
    return None


def _extract_generic_price(card: dict[str, Any]) -> Optional[float]:
    for key in ("price", "marketPrice", "current_price", "currentPrice"):
        price = _normalize_price_value(card.get(key))
        if price is not None:
            return price
    prices = card.get("prices")
    if isinstance(prices, dict):
        for value in prices.values():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    if nested_key in _SEVEN_DAY_AVERAGE_KEYS:
                        continue
                    price = _normalize_price_value(nested_value)
                    if price is not None:
                        return price
            else:
                price = _normalize_price_value(value)
                if price is not None:
                    return price
    return None


def _extract_nested_price(
    data: Any, keys: tuple[str, ...],
) -> Optional[float]:
    if not isinstance(data, dict):
        return None
    for key in keys:
        price = _normalize_price_value(data.get(key))
        if price is not None:
            return price
    for value in data.values():
        if isinstance(value, dict):
            price = _extract_nested_price(value, keys)
            if price is not None:
                return price
    return None


def _extract_7d_average_price(card: dict[str, Any]) -> Optional[float]:
    prices = card.get("prices")
    price = _extract_nested_price(prices, _SEVEN_DAY_AVERAGE_KEYS)
    if price is not None:
        return price

    cardmarket = card.get("cardmarket") or card.get("cardMarket") or {}
    if isinstance(cardmarket, dict):
        price = _extract_nested_price(cardmarket.get("prices"), _SEVEN_DAY_AVERAGE_KEYS)
        if price is not None:
            return price

    tcgplayer = card.get("tcgplayer") or card.get("tcgPlayer") or {}
    if isinstance(tcgplayer, dict):
        price = _extract_nested_price(tcgplayer.get("prices"), _SEVEN_DAY_AVERAGE_KEYS)
        if price is not None:
            return price

    return None


def _extract_card_price(card: dict[str, Any]) -> Optional[float]:
    for extractor in (
        _extract_cardmarket_price,
        _extract_tcgplayer_price,
        _extract_generic_price,
    ):
        price = extractor(card)
        if price is not None:
            return price
    return None


def _build_cards_endpoint(
    rapidapi_host: Optional[str], *path_parts: str
) -> str:
    """Return an absolute RapidAPI endpoint for the given cards resource path."""

    host = rapidapi_host or RAPIDAPI_DEFAULT_HOST
    if "://" not in host:
        host = f"https://{host}"
    parsed = urlparse(host)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path
    base_path = parsed.path.rstrip("/")
    extra_path = "/".join(part.strip("/") for part in path_parts if part)
    if base_path:
        if extra_path:
            path = f"{base_path.strip('/')}/{extra_path}"
        else:
            path = base_path.strip("/")
    else:
        path = extra_path
    path = path.strip("/")
    return f"{scheme}://{netloc}/{path}" if path else f"{scheme}://{netloc}"


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


def _extract_shop_url(card: dict[str, Any]) -> Optional[str]:
    candidates: list[str] = []

    def _add_candidate(value: Any) -> None:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                candidates.append(trimmed)

    for key in ("cardmarket", "cardMarket", "tcgplayer", "tcgPlayer"):
        container = card.get(key)
        if isinstance(container, dict):
            for field in (
                "url",
                "website",
                "websiteUrl",
                "productUrl",
                "productURL",
                "directLowUrl",
                "directLowURL",
                "directHighUrl",
                "directHighURL",
                "link",
            ):
                _add_candidate(container.get(field))

    for key in ("purchaseUrls", "purchase_urls", "urls", "links"):
        container = card.get(key)
        if isinstance(container, dict):
            for value in container.values():
                _add_candidate(value)
        elif isinstance(container, (list, tuple, set)):
            for value in container:
                _add_candidate(value)

    return candidates[0] if candidates else None


def _extract_description_text(card: dict[str, Any]) -> Optional[str]:
    snippets: list[str] = []

    def _append(value: Any, *, prefix: str | None = None) -> None:
        text_value = _normalize_text_field(value)
        if not text_value:
            return
        candidate = text_value.strip()
        if not candidate:
            return
        if prefix:
            prefix_value = prefix.strip()
            if prefix_value:
                candidate = f"{prefix_value}: {candidate}"
        if candidate not in snippets:
            snippets.append(candidate)

    for key in ("flavorText", "flavor_text", "flavor", "description", "text"):
        _append(card.get(key))

    rules = card.get("rules")
    if isinstance(rules, (list, tuple, set)):
        for rule in rules:
            _append(rule)

    for key in ("abilities", "attacks", "skills"):
        container = card.get(key)
        if not isinstance(container, list):
            continue
        for item in container:
            if isinstance(item, dict):
                label = _normalize_text_field(item.get("name") or item.get("label"))
                _append(
                    item.get("text")
                    or item.get("effect")
                    or item.get("description"),
                    prefix=label,
                )
            else:
                _append(item)

    for key in ("ability", "skill"):
        ability = card.get(key)
        if isinstance(ability, dict):
            label = _normalize_text_field(ability.get("name") or ability.get("label"))
            _append(
                ability.get("text")
                or ability.get("effect")
                or ability.get("description"),
                prefix=label,
            )
        else:
            _append(ability)

    info_fields = card.get("info") or card.get("card_text")
    if info_fields:
        _append(info_fields)

    return "\n\n".join(snippets) if snippets else None


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
    card_number_clean = text.sanitize_number(card_number_part.casefold())
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

    icon_slug, set_icon_path = set_utils.resolve_cached_set_icon(
        episode,
        set_code=set_code_value,
        set_name=set_name_value,
    )

    rarity_symbol = (
        card.get("rarity_symbol")
        or card.get("raritySymbol")
        or card.get("rarity_icon")
        or card.get("rarityIcon")
        or episode.get("rarity_symbol")
        or episode.get("raritySymbol")
    )
    if isinstance(rarity_symbol, dict):
        symbol_value = None
        for key in ("url", "image", "icon", "src", "default"):
            value = rarity_symbol.get(key)
            if isinstance(value, str) and value.strip():
                symbol_value = value.strip()
                break
        rarity_symbol = symbol_value
    if isinstance(rarity_symbol, str):
        rarity_symbol = rarity_symbol.strip() or None
    else:
        rarity_symbol = None

    rarity_symbol_remote = rarity_symbol
    rarity_symbol_local = resolve_rarity_icon_path(rarity)
    if rarity_symbol_local:
        rarity_symbol = rarity_symbol_local
    else:
        rarity_symbol = rarity_symbol_remote

    image_small, image_large = _extract_images(card)
    card_id_value = _normalize_text_field(
        card.get("id")
        or card.get("card_id")
        or card.get("cardId")
        or card.get("uuid")
        or card.get("cardUuid")
        or card.get("tcgplayerProductId")
    )
    card_id = card_id_value.strip() if isinstance(card_id_value, str) else None

    price_eur = _extract_card_price(card)
    price_7d_average_eur = _extract_7d_average_price(card)

    price_pln = None
    price_7d_average_pln = None
    if price_eur is not None or price_7d_average_eur is not None:
        rate = get_eur_pln_rate()
    else:
        rate = None
    if rate is not None:
        # For cards: add VAT markup (1.24) because cards are sold with VAT included
        if price_eur is not None:
            price_pln = round(price_eur * rate * 1.24, 2)
        if price_7d_average_eur is not None:
            price_7d_average_pln = round(price_7d_average_eur * rate * 1.24, 2)

    description = _extract_description_text(card)
    shop_url = _extract_shop_url(card)

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
        "set_icon_path": set_icon_path,
        "set_icon_slug": icon_slug,
        "rarity_symbol": rarity_symbol,
        "rarity_symbol_remote": rarity_symbol_remote,
        "price": price_pln,
        "price_7d_average": price_7d_average_pln,
        "description": description,
        "shop_url": shop_url,
        "id": card_id,
    }


def build_product_payload(product: dict[str, Any]) -> Optional[dict[str, Any]]:
    episode = product.get("episode") or product.get("set") or {}
    set_name_value = (
        episode.get("name")
        or product.get("set_name")
        or product.get("setName")
        or ""
    )
    set_code_value = (
        episode.get("code")
        or episode.get("slug")
        or episode.get("id")
        or product.get("set_code")
        or product.get("setCode")
    )

    release_date = _normalize_text_field(
        episode.get("released_at")
        or episode.get("releaseDate")
        or episode.get("release_date")
        or product.get("releaseDate")
        or product.get("release_date")
    )
    set_icon = (
        episode.get("symbol")
        or episode.get("logo")
        or episode.get("icon")
        or product.get("set_symbol")
        or product.get("set_logo")
    )

    icon_slug, set_icon_path = set_utils.resolve_cached_set_icon(
        episode,
        set_code=set_code_value,
        set_name=set_name_value,
    )

    image_small, image_large = _extract_images(product)
    product_id_value = _normalize_text_field(
        product.get("id")
        or product.get("product_id")
        or product.get("productId")
        or product.get("uuid")
        or product.get("productUuid")
        or product.get("tcgplayerProductId")
    )
    product_id = product_id_value.strip() if isinstance(product_id_value, str) else None

    price_eur = _extract_card_price(product)
    price_7d_average_eur = _extract_7d_average_price(product)

    price_pln = None
    price_7d_average_pln = None
    if price_eur is not None or price_7d_average_eur is not None:
        rate = get_eur_pln_rate()
    else:
        rate = None
    if rate is not None:
        if price_eur is not None:
            price_pln = round(price_eur * rate, 2)
        if price_7d_average_eur is not None:
            price_7d_average_pln = round(price_7d_average_eur * rate, 2)

    description = _extract_description_text(product)
    shop_url = _extract_shop_url(product)

    return {
        "name": product.get("name") or "",
        "set_name": set_name_value,
        "set_code": set_code_value,
        "image_small": image_small,
        "image_large": image_large,
        "release_date": release_date,
        "set_icon": set_icon,
        "set_icon_path": set_icon_path,
        "set_icon_slug": icon_slug,
        "price": price_pln,
        "price_7d_average": price_7d_average_pln,
        "description": description,
        "shop_url": shop_url,
        "id": product_id,
    }



def search_cards(
    *,
    name: str,
    number: str | None = None,
    set_name: Optional[str] = None,
    set_code: Optional[str] = None,
    total: Optional[str] = None,
    limit: int = 10,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> tuple[list[dict], int, int]:
    if not name:
        return [], 0, 0

    http = session or requests

    try:
        page_value = int(page)
    except (TypeError, ValueError):
        page_value = 1
    page_value = max(1, page_value)

    try:
        per_page_value = int(per_page)
    except (TypeError, ValueError):
        per_page_value = limit if limit and limit > 0 else 20
    per_page_value = max(1, min(per_page_value, 250))

    number_part = ""
    number_total = ""
    if number:
        number_part, number_total = _split_number_total(str(number))
    if total:
        _, forced_total = _split_number_total(str(total))
        number_total = forced_total or number_total
    number_part_normalized = number_part.casefold() if number_part else ""
    number_clean = (
        text.sanitize_number(number_part_normalized) if number_part_normalized else ""
    )
    total_clean = text.sanitize_number(number_total) if number_total else ""

    name_api = text.normalize(name, keep_spaces=True)
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    url = _build_cards_endpoint(api_host_value, "cards", "search")
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

    rapid_search_parts: list[str] = []
    if name_api:
        rapid_search_parts.append(name_api)
    if number_clean:
        rapid_search_parts.append(number_clean)
    if set_name:
        set_query = text.normalize(set_name, keep_spaces=True)
        if set_query:
            rapid_search_parts.append(set_query)
    if set_code:
        set_code_clean = set_utils.clean_code(set_code)
        if set_code_clean:
            rapid_search_parts.append(set_code_clean)
            canonical_set_code = set_utils.resolve_canonical_set_slug(set_code)
            if (
                canonical_set_code
                and canonical_set_code != set_code_clean
            ):
                rapid_search_parts.append(canonical_set_code)
    if total_clean:
        rapid_search_parts.append(total_clean)
    deduped_parts: list[str] = []
    seen_parts: set[str] = set()
    for part in rapid_search_parts:
        if not part or part in seen_parts:
            continue
        deduped_parts.append(part)
        seen_parts.add(part)
    query_value = " ".join(deduped_parts)
    if not query_value:
        return [], 0, 0

    # Debug logging (set to DEBUG level to avoid production log clutter)
    logger.debug(f"search_cards: query='{query_value}' (name={name}, number={number}, set_code={set_code})")

    max_results = 100
    limit_value = limit if limit and limit > 0 else per_page_value
    limit_value = min(limit_value, max_results)
    aggregated_cards: list[dict[str, Any]] = []
    total_count_remote = 0
    inferred_total = 0
    current_page = page_value

    while len(aggregated_cards) < max_results:
        params = {
            "search": query_value,
            "page": str(current_page),
            "pageSize": str(per_page_value),
        }
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order

        try:
            response = http.get(url, params=params, headers=headers, timeout=timeout)
        except requests.Timeout:
            logger.warning("Request timed out")
            break
        except (requests.RequestException, ValueError) as exc:  # pragma: no cover
            logger.warning("Fetching cards from RapidAPI failed: %s", exc)
            break

        if response.status_code != 200:
            logger.warning("API error: %s", response.status_code)
            break

        try:
            cards_payload = response.json()
        except ValueError:
            logger.warning("RapidAPI returned invalid JSON payload")
            break

        cards_page: list[dict[str, Any]] = []
        page_total_count = 0
        if isinstance(cards_payload, dict):
            cards_page = (
                cards_payload.get("data")
                or cards_payload.get("cards")
                or []
            )
            page_total_count = int(cards_payload.get("totalCount") or 0)
        elif isinstance(cards_payload, list):
            cards_page = cards_payload

        if page_total_count:
            total_count_remote = page_total_count

        if not isinstance(cards_page, list) or not cards_page:
            break

        aggregated_cards.extend(cards_page)
        if len(aggregated_cards) >= limit_value:
            break

        fetched_total = (current_page - page_value) * per_page_value + len(cards_page)
        inferred_total = max(inferred_total, fetched_total)

        if len(aggregated_cards) >= max_results:
            break
        if total_count_remote and fetched_total >= total_count_remote:
            break
        if len(cards_page) < per_page_value:
            break

        current_page += 1

    cards = aggregated_cards
    total_count = total_count_remote or inferred_total

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
            strong_name_match = False
            if card_name_norm == name_norm:
                strong_name_match = True
            elif name_norm in card_name_norm or card_name_norm in name_norm:
                strong_name_match = True

            if strong_name_match:
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
        if len(results) >= limit_value:
            break

    if not total_count:
        total_count = len(results)

    total_count = max(total_count, len(results))
    filtered_total = len(results)

    return results, filtered_total, total_count


def search_products(
    *,
    name: str,
    set_name: Optional[str] = None,
    set_code: Optional[str] = None,
    limit: int = 10,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> tuple[list[dict], int, int]:
    if not name:
        return [], 0, 0

    http = session or requests

    try:
        page_value = int(page)
    except (TypeError, ValueError):
        page_value = 1
    page_value = max(1, page_value)

    try:
        per_page_value = int(per_page)
    except (TypeError, ValueError):
        per_page_value = limit if limit and limit > 0 else 20
    per_page_value = max(1, min(per_page_value, 250))

    name_api = text.normalize(name, keep_spaces=True)
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    url = _build_cards_endpoint(api_host_value, "products", "search")
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

    rapid_search_parts: list[str] = []
    if name_api:
        rapid_search_parts.append(name_api)
    if set_name:
        set_query = text.normalize(set_name, keep_spaces=True)
        if set_query:
            rapid_search_parts.append(set_query)
    if set_code:
        set_code_clean = set_utils.clean_code(set_code)
        if set_code_clean:
            rapid_search_parts.append(set_code_clean)
            canonical_set_code = set_utils.resolve_canonical_set_slug(set_code)
            if (
                canonical_set_code
                and canonical_set_code != set_code_clean
            ):
                rapid_search_parts.append(canonical_set_code)

    deduped_parts: list[str] = []
    seen_parts: set[str] = set()
    for part in rapid_search_parts:
        if not part or part in seen_parts:
            continue
        deduped_parts.append(part)
        seen_parts.add(part)
    query_value = " ".join(deduped_parts)
    if not query_value:
        return [], 0, 0

    max_results = 100
    limit_value = limit if limit and limit > 0 else per_page_value
    limit_value = min(limit_value, max_results)
    aggregated_products: list[dict[str, Any]] = []
    total_count_remote = 0
    inferred_total = 0
    current_page = page_value

    while len(aggregated_products) < max_results:
        params = {
            "search": query_value,
            "page": str(current_page),
            "pageSize": str(per_page_value),
        }
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order

        try:
            response = http.get(url, params=params, headers=headers, timeout=timeout)
        except requests.Timeout:
            logger.warning("Request timed out")
            break
        except (requests.RequestException, ValueError) as exc:  # pragma: no cover
            logger.warning("Fetching products from RapidAPI failed: %s", exc)
            break

        if response.status_code != 200:
            logger.warning("API error: %s", response.status_code)
            break

        try:
            products_payload = response.json()
        except ValueError:
            logger.warning("RapidAPI returned invalid JSON payload")
            break

        products_page: list[dict[str, Any]] = []
        page_total_count = 0
        if isinstance(products_payload, dict):
            products_page = (
                products_payload.get("data")
                or products_payload.get("products")
                or []
            )
            page_total_count = int(products_payload.get("totalCount") or 0)
        elif isinstance(products_payload, list):
            products_page = products_payload

        if page_total_count:
            total_count_remote = page_total_count

        if not isinstance(products_page, list) or not products_page:
            break

        aggregated_products.extend(products_page)
        if len(aggregated_products) >= limit_value:
            break

        fetched_total = (current_page - page_value) * per_page_value + len(products_page)
        inferred_total = max(inferred_total, fetched_total)

        if len(aggregated_products) >= max_results:
            break
        if total_count_remote and fetched_total >= total_count_remote:
            break
        if len(products_page) < per_page_value:
            break

        current_page += 1

    products = aggregated_products
    total_count = total_count_remote or inferred_total

    suggestions: list[dict[str, Any]] = []
    for product in products or []:
        payload = build_product_payload(product)
        if not payload:
            continue
        suggestions.append(payload)

    if not total_count:
        total_count = len(suggestions)

    total_count = max(total_count, len(suggestions))
    filtered_total = len(suggestions)

    return suggestions, filtered_total, total_count


def get_latest_products(
    *,
    limit: int = 10,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> list[dict]:
    http = session or requests

    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    url = _build_cards_endpoint(api_host_value, "products")
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

    params = {
        "page": "1",
        "pageSize": "100",
        # Note: Do NOT add sort/order parameters here
        # The API's default sorting returns the newest products correctly
        # Adding sort=releaseDate&order=desc actually returns OLD products (bug in API)
    }

    try:
        response = http.get(url, params=params, headers=headers, timeout=timeout)
    except requests.Timeout:
        logger.warning("Request timed out")
        return []
    except (requests.RequestException, ValueError) as exc:  # pragma: no cover
        logger.warning("Fetching latest products from RapidAPI failed: %s", exc)
        return []

    if response.status_code != 200:
        logger.warning("API error: %s", response.status_code)
        return []

    try:
        products_payload = response.json()
    except ValueError:
        logger.warning("RapidAPI returned invalid JSON payload")
        return []

    products_page: list[dict[str, Any]] = []
    if isinstance(products_payload, dict):
        products_page = (
            products_payload.get("data")
            or products_payload.get("products")
            or []
        )
    elif isinstance(products_payload, list):
        products_page = products_payload

    if not isinstance(products_page, list) or not products_page:
        return []

    suggestions: list[dict[str, Any]] = []
    for product in products_page or []:
        payload = build_product_payload(product)
        if not payload:
            continue
        suggestions.append(payload)

    # Filter products from the last 90 days and next 60 days
    # This shows recent releases and upcoming products, excluding old and far-future products
    today = dt.date.today()
    past_cutoff_date = today - dt.timedelta(days=90)
    future_cutoff_date = today + dt.timedelta(days=60)

    filtered_products = []
    for product in suggestions:
        # Filter by product type: only ETB, Booster Box, and Booster
        name = product.get("name", "").lower()

        # Check if product is one of the allowed types
        is_etb = "elite trainer box" in name or "etb" in name
        is_booster_box = "booster box" in name
        is_booster = (
            "booster" in name
            and "box" not in name
            and "case" not in name
            and "bundle" not in name
        )

        if not (is_etb or is_booster_box or is_booster):
            # Skip products that are not ETB, Booster Box, or Booster
            continue

        # Filter by release date: show products from last 90 days OR next 60 days
        release_date_str = product.get("release_date")
        if not release_date_str:
            # Include products without date (better than excluding them)
            filtered_products.append(product)
            continue

        release_date = _parse_history_date(release_date_str)
        if release_date and past_cutoff_date <= release_date <= future_cutoff_date:
            filtered_products.append(product)
    
    # Sort by release date descending to show newest first
    filtered_products.sort(key=lambda p: p.get("release_date") or "", reverse=True)
    
    # If we have filtered products, return them; otherwise fallback to all suggestions
    if filtered_products:
        return filtered_products[:limit]
    
    # Fallback: return all products if none match the filter
    suggestions.sort(key=lambda p: p.get("release_date") or "", reverse=True)
    return suggestions[:limit]





def list_set_cards(
    set_code: str,
    *,
    limit: int = 12,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch cards for a set from the API.
    
    Uses /episodes/{id}/cards endpoint with the API's episode ID.
    Falls back to search query if no mapping is found.
    """
    if not set_code:
        return [], 0

    http = session or requests
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

    # Try to get API episode ID from mapping
    set_mapping = _load_set_code_mapping()
    api_info = set_mapping.get(set_code.strip())
    
    page = 1
    page_size = 50  # API returns max 20 per page for episodes endpoint
    results: list[dict[str, Any]] = []
    fetched_total = 0
    request_count = 0
    total_count = 0

    if api_info and api_info.get("api_id"):
        # Use /episodes/{id}/cards endpoint (preferred)
        api_id = api_info["api_id"]
        logger.info("Using episodes endpoint for set %s (api_id=%s)", set_code, api_id)
        
        while True:
            url = _build_cards_endpoint(api_host_value, f"episodes/{api_id}/cards")
            params = {
                "page": str(page),
                "pageSize": str(page_size),
            }
            try:
                response = http.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
            except requests.Timeout:
                request_count += 1
                logger.warning("Request timed out for set %s page %d", set_code, page)
                break
            except (requests.RequestException, ValueError) as exc:
                request_count += 1
                logger.warning("Fetching cards for set %s failed: %s", set_code, exc)
                break
            else:
                request_count += 1
                if response.status_code != 200:
                    logger.warning("API error for set %s: %s", set_code, response.status_code)
                    break
                payload = response.json()

            cards = []
            if isinstance(payload, dict):
                cards = payload.get("data") or []
                total_count = int(payload.get("results") or payload.get("totalCount") or 0)
                paging = payload.get("paging", {})
                total_pages = paging.get("total", 1)
            elif isinstance(payload, list):
                cards = payload
                total_pages = 1

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
                # Add set code to the card
                if not item.get("set_code"):
                    item["set_code"] = set_code
                results.append(item)

            fetched_total += len(cards)
            logger.debug("Set %s: page %d/%d, got %d cards, total %d", 
                        set_code, page, total_pages, len(cards), fetched_total)
            
            if limit and limit > 0 and len(results) >= limit:
                break

            if page >= total_pages:
                break
            
            page += 1
    else:
        # Fallback: use search query (old method)
        logger.info("No API mapping for set %s, using search fallback", set_code)
        url = _build_cards_endpoint(api_host_value, "cards")
        
        def _escape_query(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', r"\"")

        set_value = set_code.strip()
        normalized = text.normalize(set_code, keep_spaces=True)
        escaped_value = _escape_query(set_value)
        
        def _map_query_field(field: str) -> str:
            mapping = {
                "set.id": "setId",
                "set.ptcgoCode": "setPtcgoCode",
                "set.name": "setName",
            }
            return mapping.get(field, field.replace(".", ""))

        set_filters = {
            f'{_map_query_field("set.id")}:"{escaped_value}"',
            f'{_map_query_field("set.ptcgoCode")}:"{escaped_value}"',
            f'{_map_query_field("set.name")}:"*{escaped_value}*"',
        }
        if normalized and normalized != set_value:
            escaped_normalized = _escape_query(normalized)
            set_filters.add(f'{_map_query_field("set.id")}:"{escaped_normalized}"')
            set_filters.add(f'{_map_query_field("set.ptcgoCode")}:"{escaped_normalized}"')
            set_filters.add(f'{_map_query_field("set.name")}:"*{escaped_normalized}*"')

        query = "(" + " OR ".join(sorted(set_filters)) + ")"
        page_size = 250

        while True:
            params = {
                "search": query,
                "page": str(page),
                "pageSize": str(page_size),
                "sort": "number",
            }
            try:
                response = http.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
            except requests.Timeout:
                request_count += 1
                logger.warning("Request timed out")
                break
            except (requests.RequestException, ValueError) as exc:
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
    
    logger.info("Set %s: fetched %d cards in %d requests", set_code, len(results), request_count)
    return results, request_count


def _normalize_history_date_param(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed = _parse_history_date(text)
        if parsed:
            return parsed.isoformat()
        return text
    parsed = _parse_history_date(value)
    if parsed:
        return parsed.isoformat()
    return None


def fetch_card_price_history(
    card_id: str,
    *,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
    market: Optional[str] = None,
    currency: Optional[str] = None,
    date_from: Any | None = None,
    date_to: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch market price history for a Pokémon card via RapidAPI."""

    if not card_id:
        return []

    http = session or requests
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    url = _build_cards_endpoint(api_host_value, "cards", card_id, "history-prices")
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

    params: dict[str, str] = {"id": card_id}
    if market:
        params["market"] = market
    if currency:
        params["currency"] = currency
    if date_from is not None:
        normalized_from = _normalize_history_date_param(date_from)
        if normalized_from:
            params["date_from"] = normalized_from
    if date_to is not None:
        normalized_to = _normalize_history_date_param(date_to)
        if normalized_to:
            params["date_to"] = normalized_to

    try:
        response = http.get(url, params=params, headers=headers, timeout=timeout)
    except requests.Timeout:
        logger.warning("Price history request timed out for card %s", card_id)
        return []
    except (requests.RequestException, ValueError) as exc:  # pragma: no cover
        logger.warning("Fetching price history for %s failed: %s", card_id, exc)
        return []

    if response.status_code != 200:
        logger.warning(
            "API error while fetching price history for %s: %s",
            card_id,
            response.status_code,
        )
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.warning("Failed to decode price history payload for card %s", card_id)
        return []

    history: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        candidates = payload.get("data") or payload.get("history") or payload.get("prices")
        if candidates is None and payload:
            candidates = payload
        if isinstance(candidates, dict):
            candidates = [candidates]
        if isinstance(candidates, list):
            history = [item for item in candidates if isinstance(item, dict)]
    elif isinstance(payload, list):
        history = [item for item in payload if isinstance(item, dict)]

    return history


def fetch_product_price_history(
    product_id: str,
    *,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
    date_from: Any | None = None,
    date_to: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch market price history for a Pokémon product via RapidAPI."""

    if not product_id:
        return []

    http = session or requests
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    url = _build_cards_endpoint(api_host_value, "products", product_id, "history-prices")
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

    params: dict[str, str] = {"id": product_id}
    if date_from is not None:
        if isinstance(date_from, dt.date):
            params["date_from"] = date_from.strftime("%Y-%m-%d")
        elif isinstance(date_from, str) and date_from.strip():
            params["date_from"] = date_from.strip()
    if date_to is not None:
        if isinstance(date_to, dt.date):
            params["date_to"] = date_to.strftime("%Y-%m-%d")
        elif isinstance(date_to, str) and date_to.strip():
            params["date_to"] = date_to.strip()

    try:
        response = http.get(url, params=params, headers=headers, timeout=timeout)
    except requests.Timeout:
        logger.warning("Timeout fetching product price history for %s", product_id)
        return []
    except requests.RequestException as exc:  # pragma: no cover
        logger.warning("Fetching product price history for %s failed: %s", product_id, exc)
        return []

    if response.status_code != 200:
        logger.warning(
            "API error while fetching product price history for %s: %s",
            product_id,
            response.status_code,
        )
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.warning("Failed to decode product price history payload for %s", product_id)
        return []

    history: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        candidates = payload.get("data") or payload.get("history") or payload.get("prices")
        if candidates is None and payload:
            candidates = payload
        if isinstance(candidates, dict):
            candidates = [candidates]
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    history.append(item)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                history.append(item)

    return history


def _parse_history_date(value: Any) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, dt.date):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return None
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        try:
            return dt.datetime.utcfromtimestamp(timestamp).date()
        except (OverflowError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return _parse_history_date(int(text))
        try:
            return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y.%m.%d", "%Y%m%d"):
            try:
                return dt.datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S").date()
        except ValueError:
            pass
        try:
            numeric = float(text)
        except ValueError:
            numeric = None
        if numeric is not None:
            return _parse_history_date(numeric)
    return None


def _extract_history_date(entry: dict[str, Any]) -> Optional[dt.date]:
    for key in (
        "date",
        "day",
        "timestamp",
        "time",
        "updated",
        "updatedAt",
        "updated_at",
        "lastUpdated",
        "lastUpdate",
        "created",
        "createdAt",
    ):
        if key in entry:
            parsed = _parse_history_date(entry.get(key))
            if parsed:
                return parsed

    for nested_key in ("market", "prices", "price", "value"):
        nested = entry.get(nested_key)
        if isinstance(nested, dict) and nested is not entry:
            parsed = _extract_history_date(nested)
            if parsed:
                return parsed

    return None


def _normalize_currency_code(value: Any) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        code = text.upper()
        if code in {"PL", "PLN", "ZŁ", "ZL", "PLN.", "PL ZŁ"}:
            return "PLN"
        if code in {"EUR", "EURO", "€"}:
            return "EUR"
        return code
    if isinstance(value, dict):
        for key in ("code", "value", "currency"):
            if key in value:
                candidate = _normalize_currency_code(value.get(key))
                if candidate:
                    return candidate
    return None


def _extract_history_currency(entry: dict[str, Any]) -> Optional[str]:
    for key in ("currency", "currencyCode", "currency_code"):
        if key in entry:
            currency = _normalize_currency_code(entry.get(key))
            if currency:
                return currency
    for nested_key in ("market", "prices", "value"):
        nested = entry.get(nested_key)
        if isinstance(nested, dict) and nested is not entry:
            currency = _extract_history_currency(nested)
            if currency:
                return currency
    return None


def normalize_price_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not history:
        return []

    normalized: list[dict[str, Any]] = []
    eur_rate: Optional[float] = None

    if not isinstance(history, list) or not history or not isinstance(history[0], dict):
        return []

    history_dict = history[0]

    for date_str, price_obj in history_dict.items():
        if not isinstance(price_obj, dict):
            continue
            
        date_value = _parse_history_date(date_str)
        if not date_value:
            continue
        
        logger.info(f"Processing date: {date_str}, price_obj: {price_obj}")

        # Prioritize Cardmarket ('cm_low'), fallback to TCGPlayer
        price_value = _normalize_price_value(
            price_obj.get("cm_low") or price_obj.get("tcg_player_market")
        )
        logger.info(f"Extracted base price_value: {price_value}")
        
        if price_value is None:
            continue
            
        # Assume prices are in a foreign currency (EUR/USD) that needs conversion
        if eur_rate is None:
            eur_rate = get_eur_pln_rate()
        logger.info(f"Using EUR->PLN rate: {eur_rate}")

        if eur_rate:
            final_price = round(price_value * eur_rate, 2)
        else:
            # Fallback if EUR rate is unavailable, use original value but log it
            final_price = round(price_value, 2)
            logger.warning("EUR to PLN exchange rate not available. Using raw price value.")

        logger.info(f"Final price for {date_str}: {final_price} PLN")

        normalized.append(
            {
                "date": date_value.isoformat(),
                "price": final_price,
                "currency": "PLN" if eur_rate else "EUR", # Mark currency for clarity
            }
        )

    if not normalized:
        return []

    # Sort by date and remove duplicates
    deduped: dict[str, dict[str, Any]] = {}
    for entry in sorted(normalized, key=lambda x: x["date"]):
        deduped[entry["date"]] = entry

    return list(deduped.values())


def slice_price_history(
    history: list[dict[str, Any]], window: Optional[int] = None
) -> list[dict[str, Any]]:
    if not history:
        return []
    ordered = sorted(history, key=lambda item: item.get("date") or "")
    if window is None or window <= 0:
        return [dict(point) for point in ordered]
    return [dict(point) for point in ordered[-window:]]
