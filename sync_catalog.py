#!/usr/bin/env python3
"""CLI utility to import card data from RapidAPI into the local database."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Iterable

from kartoteka_web.database import init_db, session_scope
from kartoteka_web.services import catalog_sync


def _resolve_env(keys: Iterable[str]) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronise the local card catalogue.")
    parser.add_argument(
        "--sets",
        nargs="+",
        metavar="SET",
        help="Set codes to synchronise. Default: all known sets.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit cards fetched per set (useful for testing).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    rapidapi_key = _resolve_env(
        ("KARTOTEKA_RAPIDAPI_KEY", "POKEMONTCG_RAPIDAPI_KEY", "RAPIDAPI_KEY")
    )
    rapidapi_host = _resolve_env(
        ("KARTOTEKA_RAPIDAPI_HOST", "POKEMONTCG_RAPIDAPI_HOST", "RAPIDAPI_HOST")
    )

    init_db()
    with session_scope() as session:
        summary = catalog_sync.sync_sets(
            session,
            set_codes=args.sets,
            rapidapi_key=rapidapi_key,
            rapidapi_host=rapidapi_host,
            limit_per_set=args.limit,
        )

    logging.info(
        "Synchronised %s sets: %s new, %s updated (%s requests)",
        len(summary.set_codes),
        summary.cards_added,
        summary.cards_updated,
        summary.request_count,
    )


if __name__ == "__main__":
    main()
