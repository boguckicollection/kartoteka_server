"""Minimal helpers for working with user-defined card sets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Optional, Sequence

from . import text


SET_ICON_URL_BASE = "/icon/set"
DEFAULT_ICON_DIRECTORY = Path(__file__).resolve().parents[2] / "icon" / "set"


def clean_code(code: Optional[str]) -> Optional[str]:
    """Return a filesystem-friendly version of ``code``."""

    if not code:
        return None
    cleaned = re.sub(r"[^a-z0-9-]", "", str(code).lower())
    return cleaned or None


def slugify_set_identifier(*, set_code: Optional[str] = None, set_name: Optional[str] = None) -> str:
    """Return a URL-friendly identifier for routing card detail pages."""

    code = clean_code(set_code)
    if code:
        return code
    name = text.normalize(set_name or "", keep_spaces=True)
    if not name:
        return "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def resolve_cached_set_icon(
    set_payload: Mapping[str, object] | None = None,
    *,
    set_code: Optional[str] = None,
    set_name: Optional[str] = None,
    icons_directory: Path | str | None = None,
    url_base: str = SET_ICON_URL_BASE,
) -> tuple[Optional[str], Optional[str]]:
    """Return a cached set icon slug and URL if the file exists locally."""

    directory = Path(icons_directory) if icons_directory is not None else DEFAULT_ICON_DIRECTORY

    raw_candidates: Sequence[Optional[str]]
    if set_payload is not None:
        raw_candidates = (
            set_payload.get("id"),
            set_payload.get("code"),
            set_payload.get("setCode"),
            set_payload.get("ptcgoCode"),
            set_payload.get("name"),
            set_code,
            set_name,
        )
    else:
        raw_candidates = (set_code, set_name)

    for candidate in raw_candidates:
        if not isinstance(candidate, str):
            continue
        slug = clean_code(candidate)
        if not slug:
            continue
        try:
            icon_path = directory / f"{slug}.png"
            if icon_path.is_file():
                normalized_base = url_base.rstrip("/") or "/"
                return slug, f"{normalized_base}/{slug}.png"
        except OSError:
            return slug, None
    return None, None
