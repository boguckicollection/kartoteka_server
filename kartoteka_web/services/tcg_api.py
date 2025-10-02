"""Minimal RapidAPI Pokémon TCG helpers for catalogue operations."""

from __future__ import annotations

import logging
import time
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from ..utils import text

logger = logging.getLogger(__name__)

RAPIDAPI_DEFAULT_HOST = "pokemon-tcg-api.p.rapidapi.com"
_EUR_PLN_RATE_CACHE: dict[str, float | None] = {"value": None, "expires": 0.0}
_EUR_PLN_RATE_TTL = 60 * 60  # 1 hour

_SEVEN_DAY_AVERAGE_KEYS: tuple[str, ...] = (
    "7d_average",
    "avg7",
    "avg_7",
    "sevenDayAverage",
    "seven_day_average",
    "sevenDayAvg",
)


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
    cardmarket = (
        card.get("cardmarket")
        or card.get("cardMarket")
        or card.get("card_market")
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
    for key in ("price", "marketPrice"):
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

    image_small, image_large = _extract_images(card)
    price_eur = _extract_card_price(card)
    price_7d_average_eur = _extract_7d_average_price(card)

    price_pln = None
    price_7d_average_pln = None
    if price_eur is not None or price_7d_average_eur is not None:
        rate = get_eur_pln_rate()
    else:
        rate = None
    if rate is not None:
        if price_eur is not None:
            price_pln = round(price_eur * rate * 1.24, 2)
        if price_7d_average_eur is not None:
            price_7d_average_pln = round(price_7d_average_eur * rate * 1.24, 2)

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
        "rarity_symbol": rarity_symbol,
        "price": price_pln,
        "price_7d_average": price_7d_average_pln,
    }


def search_cards(
    *,
    name: str,
    number: str | None = None,
    set_name: Optional[str] = None,
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
) -> tuple[list[dict], int]:
    if not name:
        return [], 0

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
    if total_clean:
        rapid_search_parts.append(total_clean)
    query_value = " ".join(part for part in rapid_search_parts if part)
    if not query_value:
        return [], 0

    max_results = 100
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
    limit_value = limit if limit and limit > 0 else per_page_value
    limit_value = min(limit_value, max_results)
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

    total_count = min(max_results, total_count)

    return results, total_count


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
    headers: dict[str, str] = {}
    _apply_default_user_agent(headers, session)
    api_host_value, api_host_header = _normalize_host(rapidapi_host)
    url = _build_cards_endpoint(api_host_value, "cards")
    if rapidapi_key:
        headers["X-RapidAPI-Key"] = rapidapi_key
    headers["X-RapidAPI-Host"] = api_host_header

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
    page = 1
    page_size = 250
    results: list[dict[str, Any]] = []
    fetched_total = 0
    request_count = 0

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


def fetch_card_price_history(
    card_id: str,
    *,
    rapidapi_key: Optional[str] = None,
    rapidapi_host: Optional[str] = None,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
    market: Optional[str] = None,
    currency: Optional[str] = None,
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

    params: dict[str, str] = {}
    if market:
        params["market"] = market
    if currency:
        params["currency"] = currency

    try:
        response = http.get(url, params=params or None, headers=headers, timeout=timeout)
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
