"""Tools for synchronising the local card catalogue with RapidAPI data."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from sqlmodel import Session, select

from .. import models
from ..utils import sets as set_utils, text
from . import tcg_api

logger = logging.getLogger(__name__)


@dataclass
class SyncSummary:
    """Aggregate information returned after synchronising multiple sets."""

    set_codes: list[str]
    cards_added: int = 0
    cards_updated: int = 0
    request_count: int = 0


def iter_all_set_codes(data_path: Path | None = None) -> list[str]:
    """Return a flat list of all set codes defined in ``tcg_sets.json``."""

    path = data_path or set_utils.SET_DATA_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Unable to read set definitions from %s", path)
        return []

    codes: list[str] = []
    for entries in payload.values():
        if not isinstance(entries, Sequence):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            code = entry.get("code")
            if isinstance(code, str) and code.strip():
                codes.append(code.strip())
    return codes


def _normalize_price(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        text_value = text_value.replace(",", ".")
        try:
            return float(text_value)
        except ValueError:
            return None
    return None


def upsert_card_record(
    session: Session,
    payload: dict[str, object],
    *,
    timestamp: dt.datetime | None = None,
) -> tuple[models.CardRecord | None, bool, bool]:
    """Insert or update a :class:`CardRecord` from a RapidAPI payload."""

    name = str(payload.get("name") or "").strip()
    number = str(payload.get("number") or "").strip()
    set_name = str(payload.get("set_name") or "").strip()

    if not (name and number and set_name):
        return None, False, False

    now = timestamp or dt.datetime.now(dt.timezone.utc)
    number_display = str(payload.get("number_display") or number).strip() or number
    total_value_raw = payload.get("total")
    total_value = (
        text.sanitize_number(str(total_value_raw))
        if total_value_raw is not None
        else None
    )
    set_code_value = payload.get("set_code")
    set_code = str(set_code_value).strip() if set_code_value else None
    set_code_clean = set_utils.clean_code(set_code)

    stmt = select(models.CardRecord).where(
        (models.CardRecord.name == name)
        & (models.CardRecord.number == number)
        & (models.CardRecord.set_name == set_name)
    )
    record = session.exec(stmt).first()

    # Extract remote_id from payload
    remote_id_value = payload.get("id")
    remote_id = str(remote_id_value).strip() if remote_id_value else None
    
    base_kwargs = {
        "remote_id": remote_id,
        "name": name,
        "name_normalized": text.normalize(name, keep_spaces=True),
        "number": number,
        "number_display": number_display,
        "total": total_value,
        "set_name": set_name,
        "set_name_normalized": text.normalize(set_name, keep_spaces=True),
        "set_code": set_code,
        "set_code_clean": set_code_clean,
        "rarity": payload.get("rarity"),
        "artist": payload.get("artist"),
        "series": payload.get("series"),
        "release_date": payload.get("release_date"),
        "image_small": payload.get("image_small"),
        "image_large": payload.get("image_large"),
        "set_icon": payload.get("set_icon"),
        "price": _normalize_price(payload.get("price")),
        "price_7d_average": _normalize_price(payload.get("price_7d_average")),
    }

    if record is None:
        record = models.CardRecord(
            created_at=now,
            updated_at=now,
            **base_kwargs,
        )
        session.add(record)
        return record, True, False

    updated = False
    for field, value in base_kwargs.items():
        if getattr(record, field) != value:
            setattr(record, field, value)
            updated = True

    if updated:
        record.updated_at = now
    return record, False, updated


def sync_set(
    session: Session,
    set_code: str,
    *,
    rapidapi_key: str | None = None,
    rapidapi_host: str | None = None,
    limit: int | None = None,
) -> tuple[int, int, int]:
    """Synchronise a single set and return ``(added, updated, request_count)``."""

    limit_value = limit if (limit is not None and limit > 0) else 0
    cards, request_count = tcg_api.list_set_cards(
        set_code,
        limit=limit_value,
        rapidapi_key=rapidapi_key,
        rapidapi_host=rapidapi_host,
    )

    added = updated = 0
    now = dt.datetime.now(dt.timezone.utc)
    for payload in cards:
        _, created, changed = upsert_card_record(session, payload, timestamp=now)
        if created:
            added += 1
        elif changed:
            updated += 1
    return added, updated, request_count


def sync_sets(
    session: Session,
    set_codes: Iterable[str] | None = None,
    *,
    rapidapi_key: str | None = None,
    rapidapi_host: str | None = None,
    limit_per_set: int | None = None,
) -> SyncSummary:
    """Synchronise all provided sets and return aggregated statistics."""

    codes = list(set_codes or iter_all_set_codes())
    if not codes:
        return SyncSummary(set_codes=[])

    summary = SyncSummary(set_codes=codes)

    for code in codes:
        try:
            added, updated, requests = sync_set(
                session,
                code,
                rapidapi_key=rapidapi_key,
                rapidapi_host=rapidapi_host,
                limit=limit_per_set,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Synchronising set %s failed: %s", code, exc)
            continue
        summary.cards_added += added
        summary.cards_updated += updated
        summary.request_count += requests
    return summary


__all__ = [
    "SyncSummary",
    "iter_all_set_codes",
    "sync_set",
    "sync_sets",
    "upsert_card_record",
]
