"""Lightweight text helpers previously provided by the pricing module."""

from __future__ import annotations

import os
import re
import unicodedata

SEARCH_SCORE_THRESHOLD = float(os.getenv("SEARCH_SCORE_THRESHOLD", "88"))
NAME_SIMILARITY_THRESHOLD = 0.75

# Common Pokemon TCG card name patterns for fuzzy matching
POSSESSIVE_PATTERN = re.compile(r"'s\b|'s\b|`s\b", re.IGNORECASE)
APOSTROPHE_VARIANTS = re.compile(r"[''`´]")


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


def normalize_search_query(query: str) -> str:
    """
    Normalize a search query for flexible matching.
    
    Handles:
    - Case insensitivity
    - Various apostrophe styles ('s, 's, `s)
    - Common typos (orders vs order)
    - Unicode normalization
    - Extra whitespace
    
    Examples:
        "Boss's Order" -> "boss's order"
        "boss orders" -> "boss's order" (via expand_search_variants)
        "Boss'S ORDER" -> "boss's order"
    """
    if not query:
        return ""
    
    # Unicode normalization
    value = unicodedata.normalize("NFKD", query)
    value = "".join(char for char in value if not unicodedata.combining(char))
    
    # Normalize to lowercase
    value = value.lower().strip()
    
    # Normalize various apostrophe styles to standard '
    value = APOSTROPHE_VARIANTS.sub("'", value)
    
    # Normalize whitespace
    value = " ".join(value.split())
    
    return value


def expand_search_variants(query: str) -> list[str]:
    """
    Generate search query variants for flexible matching.
    
    Returns a list of possible query variants to try, ordered by likelihood.
    
    Examples:
        "boss orders" -> ["boss orders", "boss's orders", "boss's order", "boss order"]
        "bosss order" -> ["bosss order", "boss's order"]
        "professors research" -> ["professors research", "professor's research"]
    """
    if not query:
        return []
    
    normalized = normalize_search_query(query)
    variants: list[str] = [normalized]
    seen: set[str] = {normalized}
    
    def add_variant(v: str) -> None:
        v = v.strip()
        if v and v not in seen:
            variants.append(v)
            seen.add(v)
    
    # Pattern: "boss orders" -> "boss's order" (missing apostrophe + plural)
    # Try adding 's after first word
    words = normalized.split()
    if len(words) >= 2:
        # "boss orders" -> "boss's orders"
        first_word = words[0]
        rest = " ".join(words[1:])
        
        # Add possessive if missing
        if not first_word.endswith("'s"):
            add_variant(f"{first_word}'s {rest}")
            
            # Also try removing trailing 's' from second word (plural -> singular)
            # "boss's orders" -> "boss's order"
            if rest.endswith("s") and len(rest) > 1:
                add_variant(f"{first_word}'s {rest[:-1]}")
            
            # Without possessive but singular
            if rest.endswith("s") and len(rest) > 1:
                add_variant(f"{first_word} {rest[:-1]}")
    
    # Pattern: "bosss order" -> "boss's order" (typo with extra s)
    if "ss " in normalized or "sss" in normalized:
        fixed = re.sub(r"s{2,}\s", "'s ", normalized)
        fixed = re.sub(r"s{3,}", "ss", fixed)
        add_variant(fixed)
    
    # Pattern: remove possessive entirely for broader search
    # "boss's order" -> "boss order"
    without_possessive = POSSESSIVE_PATTERN.sub("", normalized)
    without_possessive = " ".join(without_possessive.split())
    add_variant(without_possessive)
    
    # Pattern: "professor research" -> "professor's research"
    # Common Pokemon TCG trainer cards with possessives
    pokemon_possessives = [
        ("professor", "professor's"),
        ("boss", "boss's"),
        ("giovanni", "giovanni's"),
        ("cynthia", "cynthia's"),
        ("marnie", "marnie's"),
        ("hop", "hop's"),
        ("leon", "leon's"),
        ("nessa", "nessa's"),
        ("raihan", "raihan's"),
        ("iris", "iris's"),
        ("iono", "iono's"),
        ("penny", "penny's"),
        ("arven", "arven's"),
        ("nemona", "nemona's"),
        ("jacq", "jacq's"),
        ("colress", "colress's"),
        ("guzma", "guzma's"),
        ("acerola", "acerola's"),
    ]
    
    for base, possessive in pokemon_possessives:
        if normalized.startswith(base + " ") and not normalized.startswith(possessive):
            add_variant(normalized.replace(base + " ", possessive + " ", 1))
    
    return variants


def is_similar_name(name1: str, name2: str, threshold: float = NAME_SIMILARITY_THRESHOLD) -> bool:
    """
    Check if two card names are similar enough to be considered a match.
    
    Uses a simple character-based similarity ratio.
    """
    if not name1 or not name2:
        return False
    
    n1 = normalize_search_query(name1)
    n2 = normalize_search_query(name2)
    
    if n1 == n2:
        return True
    
    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return True
    
    # Simple character-based similarity (Jaccard-like)
    set1 = set(n1.replace(" ", ""))
    set2 = set(n2.replace(" ", ""))
    
    if not set1 or not set2:
        return False
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return (intersection / union) >= threshold
