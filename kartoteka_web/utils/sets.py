"""Minimal helpers for working with user-defined card sets."""

from __future__ import annotations

import re
from typing import Optional

from . import text


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
