"""Utilities for synchronising the remote card catalogue locally."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any, Iterable, Tuple

from sqlmodel import Session, select

from kartoteka import pricing
from kartoteka_web import models
from kartoteka_web.utils import images as image_utils, sets as set_utils

logger = logging.getLogger(__name__)

SET_LOGO_DIR = Path("set_logos")
CATALOGUE_MARKER_FILE = Path("last_catalogue_sync.txt")
CATALOGUE_REFRESH_INTERVAL = dt.timedelta(days=1)


def _read_marker() -> dt.datetime | None:
    """Return the timestamp of the last successful catalogue sync."""

    try:
        raw = CATALOGUE_MARKER_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def _write_marker(timestamp: dt.datetime) -> None:
    """Persist ``timestamp`` as the last catalogue synchronisation moment."""

    try:
        CATALOGUE_MARKER_FILE.write_text(timestamp.isoformat(), encoding="utf-8")
    except OSError:
        logger.debug("Unable to write catalogue marker", exc_info=True)


def _should_refresh(now: dt.datetime, *, force: bool = False) -> bool:
    if force:
        return True
    last = _read_marker()
    if last is None:
        return True
    return (now - last) >= CATALOGUE_REFRESH_INTERVAL


def resolve_set_icon(set_code: str | None, set_name: str | None) -> str | None:
    code = set_utils.clean_code(set_code)
    if not code and set_name:
        code = set_utils.guess_set_code(set_name)
    if not code:
        return None
    candidate = SET_LOGO_DIR / f"{code}.png"
    if candidate.exists():
        return f"/set-logos/{candidate.name}"
    return None


def _enrich_card_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    info = set_utils.get_set_info(
        set_code=data.get("set_code"),
        set_name=data.get("set_name"),
    )
    if info:
        if info.get("era") and not data.get("series"):
            data["series"] = info.get("era")
        if info.get("total") and not data.get("total"):
            data["total"] = str(info.get("total"))
        if info.get("code") and not data.get("set_code"):
            data["set_code"] = info.get("code")
    local_icon = resolve_set_icon(data.get("set_code"), data.get("set_name"))
    if not data.get("set_icon") and local_icon:
        data["set_icon"] = local_icon
    return data


def prepare_card_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return image_utils.cache_card_images(_enrich_card_payload(payload))


def _sanitise_optional_number(value: str | None) -> str | None:
    cleaned = pricing.sanitize_number(str(value or ""))
    return cleaned or None


def ensure_record_assets(session: Session, record: "models.CardRecord") -> bool:
    updated = False
    if record and not record.set_icon:
        icon = resolve_set_icon(record.set_code, record.set_name)
        if icon:
            record.set_icon = icon
            updated = True
    if record and record.image_large and not record.image_small:
        record.image_small = record.image_large
        updated = True
    if updated:
        record.updated_at = dt.datetime.now(dt.timezone.utc)
        session.add(record)
    return updated


def upsert_card_record(
    session: Session, payload: dict[str, Any]
) -> Tuple["models.CardRecord" | None, bool]:
    data = prepare_card_payload(payload)
    name_value = (data.get("name") or "").strip()
    number_value = pricing.sanitize_number(str(data.get("number") or ""))
    if not name_value or not number_value:
        return None, False

    set_name_value = (data.get("set_name") or "").strip()
    number_display = data.get("number_display") or data.get("number") or number_value
    total_value = _sanitise_optional_number(data.get("total"))
    set_code_value = data.get("set_code") or None
    set_code_clean = set_utils.clean_code(set_code_value)
    now = dt.datetime.now(dt.timezone.utc)
    set_icon_value = data.get("set_icon") or resolve_set_icon(set_code_value, set_name_value)

    candidate = None
    if set_code_clean:
        candidate = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.number == number_value)
                & (models.CardRecord.set_code_clean == set_code_clean)
            )
        ).first()
    if candidate is None and set_name_value:
        candidate = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.number == number_value)
                & (models.CardRecord.set_name == set_name_value)
            )
        ).first()
    if candidate is None:
        candidate = session.exec(
            select(models.CardRecord).where(
                (models.CardRecord.name == name_value)
                & (models.CardRecord.number == number_value)
                & (models.CardRecord.set_name == set_name_value)
            )
        ).first()

    name_normalized = pricing.normalize(name_value)
    set_name_normalized = pricing.normalize(set_name_value) if set_name_value else None

    if candidate is None:
        record = models.CardRecord(
            name=name_value,
            name_normalized=name_normalized,
            number=number_value,
            number_display=number_display,
            total=total_value,
            set_name=set_name_value,
            set_name_normalized=set_name_normalized,
            set_code=set_code_value,
            set_code_clean=set_code_clean,
            rarity=data.get("rarity"),
            artist=data.get("artist"),
            series=data.get("series"),
            release_date=data.get("release_date"),
            image_small=data.get("image_small"),
            image_large=data.get("image_large"),
            set_icon=set_icon_value,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        return record, True

    updated = False

    def _apply(attr: str, value: Any, allow_none: bool = False) -> None:
        nonlocal updated
        if value is None and not allow_none:
            return
        if getattr(candidate, attr) != value:
            setattr(candidate, attr, value)
            updated = True

    _apply("name", name_value)
    _apply("name_normalized", name_normalized)
    _apply("number", number_value)
    _apply("number_display", number_display, allow_none=True)
    _apply("total", total_value, allow_none=True)
    _apply("set_name", set_name_value)
    _apply("set_name_normalized", set_name_normalized, allow_none=True)
    if set_code_value is not None:
        _apply("set_code", set_code_value, allow_none=True)
    if set_code_clean is not None:
        _apply("set_code_clean", set_code_clean, allow_none=True)
    if data.get("rarity"):
        _apply("rarity", data.get("rarity"), allow_none=True)
    if data.get("artist"):
        _apply("artist", data.get("artist"), allow_none=True)
    if data.get("series"):
        _apply("series", data.get("series"), allow_none=True)
    if data.get("release_date"):
        _apply("release_date", data.get("release_date"), allow_none=True)
    if data.get("image_small"):
        _apply("image_small", data.get("image_small"), allow_none=True)
    if data.get("image_large"):
        _apply("image_large", data.get("image_large"), allow_none=True)
    if set_icon_value:
        _apply("set_icon", set_icon_value, allow_none=True)

    if updated:
        candidate.updated_at = now
        session.add(candidate)
    return candidate, updated


def iter_known_set_codes() -> Iterable[str]:
    seen: set[str] = set()
    for entry in set_utils.iter_known_sets():
        code = set_utils.clean_code(entry.get("code")) if entry else None
        if code:
            seen.add(code)
    return sorted(seen)


def _has_catalogue_data(session: Session) -> bool:
    return bool(session.exec(select(models.CardRecord.id).limit(1)).first())


def refresh_catalogue(session: Session, *, now: dt.datetime | None = None, force: bool = False) -> int:
    """Synchronise the local catalogue with the remote API.

    Returns the number of records that were created or updated.
    """

    now = now or dt.datetime.now(dt.timezone.utc)
    if not force and not _has_catalogue_data(session) and not _should_refresh(now):
        # Ensure the first run always happens, even if the marker exists but the
        # database is empty for any reason.
        force = True

    if not _has_catalogue_data(session) or _should_refresh(now, force=force):
        logger.info("Synchronising card catalogue from remote API")
    else:
        return 0

    total_changed = 0
    for set_code in iter_known_set_codes():
        cards = pricing.list_set_cards(set_code, limit=0)
        if not cards:
            continue
        changed_for_set = 0
        for payload in cards:
            record, changed = upsert_card_record(session, payload)
            if record is None:
                continue
            if ensure_record_assets(session, record):
                changed = True
            if changed:
                changed_for_set += 1
        if changed_for_set:
            session.commit()
            total_changed += changed_for_set
        else:
            session.rollback()

    _write_marker(now)
    logger.info("Catalogue synchronisation completed with %s updated records", total_changed)
    return total_changed

