"""Minimal helpers for working with user-defined card sets."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional, Sequence

from . import text


SET_ICON_URL_BASE = "/icon/set"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ICON_DIRECTORY = REPO_ROOT / "icon" / "set"
SET_DATA_PATH = REPO_ROOT / "tcg_sets.json"


def _register_mapping_entry(mapping: dict[str, str], key: Optional[str], slug: str) -> None:
    """Register ``key`` -> ``slug`` in ``mapping`` if the key is valid."""

    normalized = clean_code(key)
    if not normalized:
        return
    mapping.setdefault(normalized, slug)


@lru_cache(maxsize=1)
def load_canonical_set_code_map() -> Mapping[str, str]:
    """Return a mapping of normalized identifiers to canonical set slugs."""

    mapping: dict[str, str] = {}

    try:
        raw_data = json.loads(SET_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return mapping

    for sets in raw_data.values():
        if not isinstance(sets, SequenceABC):
            continue
        for entry in sets:
            if not isinstance(entry, MappingABC):
                continue
            slug = clean_code(entry.get("code"))
            if not slug:
                continue

            _register_mapping_entry(mapping, slug, slug)
            _register_mapping_entry(mapping, entry.get("name"), slug)
            _register_mapping_entry(mapping, entry.get("abbr"), slug)

            base = re.sub(r"\d+$", "", slug)
            if base and base != slug:
                _register_mapping_entry(mapping, base, slug)

            no_leading_zero = re.sub(r"^([a-z]+)0+(\d+)$", r"\1\2", slug)
            if no_leading_zero and no_leading_zero != slug:
                _register_mapping_entry(mapping, no_leading_zero, slug)

    return mapping


def resolve_canonical_set_slug(identifier: Optional[str]) -> Optional[str]:
    """Return the canonical slug for ``identifier`` if available."""

    slug = clean_code(identifier)
    if not slug:
        return None
    mapping = load_canonical_set_code_map()
    return mapping.get(slug, slug)


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
            set_code,
            set_payload.get("code"),
            set_payload.get("setCode"),
            set_payload.get("ptcgoCode"),
            set_payload.get("slug"),
            set_payload.get("id"),
            set_payload.get("name"),
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
        canonical_slug = resolve_canonical_set_slug(slug)
        slug_candidates = []
        if canonical_slug:
            slug_candidates.append(canonical_slug)
        if canonical_slug != slug:
            slug_candidates.append(slug)

        try:
            for slug_candidate in slug_candidates:
                icon_path = directory / f"{slug_candidate}.png"
                if icon_path.is_file():
                    normalized_base = url_base.rstrip("/") or "/"
                    return slug_candidate, f"{normalized_base}/{slug_candidate}.png"
        except OSError:
            return slug_candidates[0] if slug_candidates else slug, None
    return None, None
