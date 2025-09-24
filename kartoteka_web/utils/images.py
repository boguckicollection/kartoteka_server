"""Helpers for caching card artwork locally."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional

import requests

LOGGER = logging.getLogger(__name__)

CARD_IMAGE_DIR = Path(os.getenv("CARD_IMAGE_DIR", "card_images"))
CARD_IMAGE_URL_PREFIX = os.getenv("CARD_IMAGE_URL_PREFIX", "/card-images")

_VALID_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def ensure_directory() -> Path:
    """Ensure the cache directory exists and return it."""

    try:
        CARD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - logged for visibility
        LOGGER.warning("Failed to create card image directory %s: %s", CARD_IMAGE_DIR, exc)
    return CARD_IMAGE_DIR


def _normalise_suffix(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix == ".jpe":
        return ".jpg"
    return suffix if suffix in _VALID_SUFFIXES else ""


def _guess_extension(url: str, content_type: str | None) -> str:
    candidate = _normalise_suffix(Path(url.split("?", 1)[0]).suffix)
    if candidate:
        return candidate
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if ext:
            candidate = _normalise_suffix(ext)
            if candidate:
                return candidate
    return ".jpg"


def _candidate_filename(url: str, variant: str) -> tuple[str, Optional[Path]]:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = _normalise_suffix(Path(url.split("?", 1)[0]).suffix)
    if suffix:
        filename = f"{digest}-{variant}{suffix}"
        return filename, CARD_IMAGE_DIR / filename
    return f"{digest}-{variant}", None


def _local_path(filename: str) -> str:
    prefix = CARD_IMAGE_URL_PREFIX.rstrip("/")
    return f"{prefix}/{filename}"


def cache_card_image(
    url: str,
    *,
    variant: str = "image",
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> Optional[str]:
    """Download ``url`` into the cache directory and return a local path."""

    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if value.startswith(CARD_IMAGE_URL_PREFIX):
        return value

    ensure_directory()

    filename, existing_path = _candidate_filename(value, variant)
    if existing_path and existing_path.exists():
        return _local_path(existing_path.name)

    http = session or requests
    try:
        response = http.get(value, timeout=timeout)
    except requests.RequestException as exc:  # pragma: no cover - logged in production
        LOGGER.warning("Failed to download card image %s: %s", value, exc)
        return None

    if response.status_code != 200 or not response.content:
        LOGGER.warning(
            "Failed to download card image %s (status %s)", value, response.status_code
        )
        return None

    extension = _guess_extension(value, response.headers.get("Content-Type"))
    filename = f"{hashlib.sha1(value.encode('utf-8')).hexdigest()}-{variant}{extension}"
    path = CARD_IMAGE_DIR / filename
    if not path.exists():
        try:
            path.write_bytes(response.content)
        except OSError as exc:  # pragma: no cover - logged for visibility
            LOGGER.warning("Failed to write card image %s: %s", path, exc)
            return None

    return _local_path(filename)


def ensure_local_path(
    value: Optional[str],
    *,
    variant: str = "image",
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> Optional[str]:
    """Return a cached local path for ``value`` if possible."""

    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if trimmed.startswith(CARD_IMAGE_URL_PREFIX):
        return trimmed
    return cache_card_image(trimmed, variant=variant, session=session, timeout=timeout)


def cache_card_images(
    payload: dict[str, Any],
    *,
    session: Optional[requests.sessions.Session] = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Return a copy of ``payload`` with local image paths when available."""

    data = dict(payload)
    small = ensure_local_path(
        payload.get("image_small"), variant="small", session=session, timeout=timeout
    )
    large = ensure_local_path(
        payload.get("image_large"), variant="large", session=session, timeout=timeout
    )

    small_value = small or payload.get("image_small")
    large_value = large or payload.get("image_large")

    if not small_value and large_value:
        small_value = large_value
    if not large_value and small_value:
        large_value = small_value

    data["image_small"] = small_value
    data["image_large"] = large_value
    return data

