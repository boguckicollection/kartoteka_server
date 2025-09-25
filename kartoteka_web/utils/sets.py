"""Set metadata helpers for the web UI."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from kartoteka import pricing

BASE_DIR = Path(__file__).resolve().parents[2]
SET_FILES = ("tcg_sets.json", "tcg_sets_jp.json")


def clean_code(code: Optional[str]) -> Optional[str]:
    """Return a filesystem-friendly version of ``code``."""

    if not code:
        return None
    cleaned = re.sub(r"[^a-z0-9-]", "", str(code).lower())
    return cleaned or None


def normalise_name(name: Optional[str]) -> Optional[str]:
    """Return a normalised key for ``name`` using the pricing helper."""

    if not name:
        return None
    value = pricing.normalize(name, keep_spaces=False)
    return value or None


@lru_cache(maxsize=1)
def _load_indices() -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Return lookup tables indexed by set code and set name."""

    by_code: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for filename in SET_FILES:
        path = BASE_DIR / filename
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):  # pragma: no cover - defensive
            continue
        for era, sets in (payload or {}).items():
            for item in sets or []:
                entry = {
                    "code": item.get("code"),
                    "name": item.get("name"),
                    "abbr": item.get("abbr"),
                    "total": item.get("total"),
                    "era": era,
                }
                code_key = clean_code(entry.get("code"))
                name_key = normalise_name(entry.get("name"))
                if code_key:
                    by_code[code_key] = entry
                if name_key and name_key not in by_name:
                    by_name[name_key] = entry
    return by_code, by_name


def get_set_info(*, set_code: Optional[str] = None, set_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return metadata for the given set or ``None`` when unknown."""

    index_code, index_name = _load_indices()
    code_key = clean_code(set_code)
    if code_key and code_key in index_code:
        return index_code[code_key]
    name_key = normalise_name(set_name)
    if name_key and name_key in index_name:
        return index_name[name_key]
    return None


def guess_set_code(set_name: Optional[str]) -> Optional[str]:
    """Return the known code for ``set_name`` when possible."""

    info = get_set_info(set_name=set_name)
    if not info:
        return None
    code = clean_code(info.get("code"))
    return code


def slugify_set_identifier(*, set_code: Optional[str] = None, set_name: Optional[str] = None) -> str:
    """Return a URL-friendly identifier for routing card detail pages."""

    code = clean_code(set_code)
    if code:
        return code
    name = pricing.normalize(set_name or "", keep_spaces=True)
    if not name:
        return "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def iter_known_sets() -> list[Dict[str, Any]]:
    """Return metadata for every known set."""

    index_code, _ = _load_indices()
    return list(index_code.values())
