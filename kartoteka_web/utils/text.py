"""Lightweight text helpers previously provided by the pricing module."""

from __future__ import annotations

import os
import unicodedata

SEARCH_SCORE_THRESHOLD = float(os.getenv("SEARCH_SCORE_THRESHOLD", "88"))
NAME_SIMILARITY_THRESHOLD = 0.75


def sanitize_number(value: str) -> str:
    """Return ``value`` without leading zeros."""

    text = (value or "").strip()
    if not text:
        return ""
    return text.lstrip("0") or "0"


def normalize(text: str, keep_spaces: bool = False) -> str:
    """Normalise ``text`` for catalogue lookups and searches."""

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
