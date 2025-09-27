"""Utilities for synchronising the remote card catalogue locally."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Tuple

from sqlalchemy import text
from sqlmodel import Session, select

from kartoteka import pricing
from kartoteka_web import models
from kartoteka_web.utils import images as image_utils, sets as set_utils

logger = logging.getLogger(__name__)

SET_LOGO_DIR = Path("set_logos")
CATALOGUE_MARKER_FILE = Path("last_catalogue_sync.txt")
CATALOGUE_PROGRESS_FILE = Path("last_catalogue_set.txt")
CATALOGUE_REFRESH_INTERVAL = dt.timedelta(days=1)
CATALOGUE_REQUEST_LIMIT = 1500


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


def _read_progress_marker() -> str | None:
    """Return the last fully processed set code, if available."""

    try:
        raw = CATALOGUE_PROGRESS_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return raw or None


def _write_progress_marker(set_code: str | None) -> None:
    """Persist the last fully processed set code for incremental syncs."""

    try:
        if not set_code:
            if CATALOGUE_PROGRESS_FILE.exists():
                CATALOGUE_PROGRESS_FILE.unlink()
            return
        CATALOGUE_PROGRESS_FILE.write_text(set_code, encoding="utf-8")
    except OSError:
        logger.debug("Unable to write catalogue progress marker", exc_info=True)


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


def _sync_cardrecord_search_entry(
    session: Session,
    *,
    card_id: int,
    name_normalized: str,
    set_name_normalized: str | None,
) -> None:
    session.exec(
        text("DELETE FROM cardrecord_search WHERE card_id = :card_id").bindparams(
            card_id=card_id
        )
    )
    session.exec(
        text(
            """
            INSERT INTO cardrecord_search (card_id, name_normalized, set_name_normalized)
            VALUES (:card_id, :name_normalized, :set_name_normalized)
            """
        ).bindparams(
            card_id=card_id,
            name_normalized=name_normalized,
            set_name_normalized=set_name_normalized,
        )
    )


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
        session.flush()
        if record.id is not None:
            _sync_cardrecord_search_entry(
                session,
                card_id=record.id,
                name_normalized=record.name_normalized,
                set_name_normalized=record.set_name_normalized,
            )
        return record, True

    updated = False
    fts_fields_updated = False

    def _apply(attr: str, value: Any, allow_none: bool = False) -> None:
        nonlocal updated
        if value is None and not allow_none:
            return
        if getattr(candidate, attr) != value:
            setattr(candidate, attr, value)
            updated = True

    _apply("name", name_value)
    previous_name_norm = candidate.name_normalized
    _apply("name_normalized", name_normalized)
    if previous_name_norm != candidate.name_normalized:
        fts_fields_updated = True
    _apply("number", number_value)
    _apply("number_display", number_display, allow_none=True)
    _apply("total", total_value, allow_none=True)
    _apply("set_name", set_name_value)
    previous_set_norm = candidate.set_name_normalized
    _apply("set_name_normalized", set_name_normalized, allow_none=True)
    if previous_set_norm != candidate.set_name_normalized:
        fts_fields_updated = True
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
        session.flush()
        if candidate.id is not None and fts_fields_updated:
            _sync_cardrecord_search_entry(
                session,
                card_id=candidate.id,
                name_normalized=candidate.name_normalized,
                set_name_normalized=candidate.set_name_normalized,
            )
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


def refresh_catalogue(
    session: Session,
    *,
    now: dt.datetime | None = None,
    force: bool = False,
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> int:
    """Synchronise the local catalogue with the remote API.

    Returns the number of records that were created or updated.
    """

    now = now or dt.datetime.now(dt.timezone.utc)

    def _notify(event: str, **payload: Any) -> None:
        if not progress:
            return
        try:
            progress(event, dict(payload))
        except Exception:  # pragma: no cover - defensive guard around hooks
            logger.warning("Catalogue progress hook raised during %s", event, exc_info=True)

    if not force and not _has_catalogue_data(session) and not _should_refresh(now):
        # Ensure the first run always happens, even if the marker exists but the
        # database is empty for any reason.
        force = True

    if not _has_catalogue_data(session) or _should_refresh(now, force=force):
        logger.info("Synchronising card catalogue from remote API")
    else:
        _notify("skipped", reason="Catalogue already up-to-date", force=force)
        return 0

    set_codes = list(iter_known_set_codes())
    total_sets = len(set_codes)
    _notify("start", total_sets=total_sets, force=force)
    last_processed = _read_progress_marker()
    start_index = 0
    if last_processed:
        try:
            start_index = set_codes.index(last_processed) + 1
        except ValueError:
            start_index = 0
    if start_index >= total_sets:
        start_index = 0

    if start_index:
        next_set = set_codes[start_index]
        logger.info(
            "Resuming catalogue sync from set %s (%s/%s)",
            next_set,
            start_index + 1,
            total_sets,
        )
        _notify("resume", next_set=next_set, index=start_index + 1, total_sets=total_sets)

    total_changed = 0
    requests_used = 0
    processed_sets = 0
    processed_cards = 0
    last_completed_set: str | None = None
    for position, set_code in enumerate(set_codes[start_index:], start=start_index):
        if requests_used >= CATALOGUE_REQUEST_LIMIT:
            logger.info(
                "Reached catalogue request limit (%s/%s); pausing sync",
                requests_used,
                CATALOGUE_REQUEST_LIMIT,
            )
            remaining_sets = max(total_sets - (start_index + processed_sets), 0)
            logger.info(
                "Catalogue progress: %s/%s sets, %s cards processed, %s sets remaining",
                processed_sets,
                total_sets,
                processed_cards,
                remaining_sets,
            )
            _notify(
                "limit",
                requests_used=requests_used,
                request_limit=CATALOGUE_REQUEST_LIMIT,
                processed_sets=processed_sets,
                processed_cards=processed_cards,
                remaining_sets=remaining_sets,
            )
            break

        logger.info(
            "Synchronising set %s (%s/%s) [request %s/%s]",
            set_code,
            position + 1,
            total_sets,
            requests_used + 1,
            CATALOGUE_REQUEST_LIMIT,
        )
        _notify(
            "set.start",
            set_code=set_code,
            index=position + 1,
            total_sets=total_sets,
            request_number=requests_used + 1,
            request_limit=CATALOGUE_REQUEST_LIMIT,
        )
        cards = pricing.list_set_cards(set_code, limit=0)
        card_count = len(cards or [])
        if not cards:
            requests_used += 1
            processed_sets += 1
            processed_cards += card_count
            last_completed_set = set_code
            remaining_sets = max(total_sets - (start_index + processed_sets), 0)
            logger.info(
                "Catalogue progress: %s/%s sets, %s cards processed, %s sets remaining",
                processed_sets,
                total_sets,
                processed_cards,
                remaining_sets,
            )
            _notify(
                "set.complete",
                set_code=set_code,
                index=position + 1,
                total_sets=total_sets,
                card_count=card_count,
                changed=0,
                processed_sets=processed_sets,
                processed_cards=processed_cards,
                remaining_sets=remaining_sets,
            )
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
        requests_used += 1
        processed_sets += 1
        processed_cards += card_count
        last_completed_set = set_code
        remaining_sets = max(total_sets - (start_index + processed_sets), 0)
        logger.info(
            "Catalogue progress: %s/%s sets, %s cards processed, %s sets remaining",
            processed_sets,
            total_sets,
            processed_cards,
            remaining_sets,
        )
        _notify(
            "set.complete",
            set_code=set_code,
            index=position + 1,
            total_sets=total_sets,
            card_count=card_count,
            changed=changed_for_set,
            processed_sets=processed_sets,
            processed_cards=processed_cards,
            remaining_sets=remaining_sets,
        )

    completed_all_sets = (start_index + processed_sets) >= total_sets and (
        requests_used < CATALOGUE_REQUEST_LIMIT or processed_sets == total_sets
    )

    if completed_all_sets:
        _write_progress_marker(None)
        _write_marker(now)
        logger.info(
            "Catalogue synchronisation completed with %s updated records using %s requests",
            total_changed,
            requests_used,
        )
        _notify(
            "complete",
            total_changed=total_changed,
            requests_used=requests_used,
            total_sets=total_sets,
            processed_sets=processed_sets,
        )
    elif last_completed_set:
        _write_progress_marker(last_completed_set)
        remaining_sets = max(total_sets - (start_index + processed_sets), 0)
        next_message = ""
        next_set_code: str | None = None
        if remaining_sets:
            next_index = start_index + processed_sets
            if next_index < total_sets:
                next_set_code = set_codes[next_index]
                next_message = f" Next run will start with set {next_set_code}."
        logger.info(
            "Catalogue synchronisation paused after set %s (%s processed, %s updated, %s/%s requests used).%s",
            last_completed_set,
            processed_sets,
            total_changed,
            requests_used,
            CATALOGUE_REQUEST_LIMIT,
            next_message,
        )
        _notify(
            "paused",
            last_completed_set=last_completed_set,
            processed_sets=processed_sets,
            total_sets=total_sets,
            total_changed=total_changed,
            requests_used=requests_used,
            request_limit=CATALOGUE_REQUEST_LIMIT,
            next_set=next_set_code,
            remaining_sets=remaining_sets,
        )
    elif total_sets == 0:
        _write_progress_marker(None)
        _write_marker(now)
        logger.info(
            "Catalogue synchronisation completed with %s updated records using %s requests",
            total_changed,
            requests_used,
        )
        _notify(
            "complete",
            total_changed=total_changed,
            requests_used=requests_used,
            total_sets=total_sets,
            processed_sets=processed_sets,
        )

    return total_changed

