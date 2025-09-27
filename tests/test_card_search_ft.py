"""Integration test ensuring catalogue search uses the FTS index."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@contextmanager
def _override_attribute(obj: object, name: str, value: object):
    original = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, original)


@pytest.fixture()
def search_db(tmp_path, monkeypatch):
    db_path = tmp_path / "search.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("KARTOTEKA_DATABASE_URL", db_url)

    from kartoteka_web import database

    try:  # pragma: no cover - defensive cleanup for previous tests
        database.engine.dispose()
    except Exception:
        pass

    connect_args = {"check_same_thread": False}
    database.engine = create_engine(db_url, echo=False, connect_args=connect_args)
    SQLModel.metadata.create_all(database.engine)
    database.init_db()

    yield database


def _seed_char_family(session: Session) -> None:
    from kartoteka_web import catalogue

    payloads = [
        {"name": "Charizard", "number": "4", "set_name": "Base Set"},
        {"name": "Charmander", "number": "9", "set_name": "Base Set"},
        {"name": "Charmeleon", "number": "24", "set_name": "Base Set"},
    ]
    for payload in payloads:
        record, created = catalogue.upsert_card_record(session, payload)
        assert record is not None
        if created:
            session.add(record)
    session.commit()


class _TrackingResult:
    def __init__(self, result, statement, store):
        self._result = result
        self._statement = statement
        self._store = store

    def all(self):
        rows = self._result.all()
        self._store.append({"statement": str(self._statement), "rowcount": len(rows)})
        return rows

    def first(self):  # pragma: no cover - convenience for potential reuse
        return self._result.first()

    def __getattr__(self, item):
        return getattr(self._result, item)


def _run_search(session: Session, *, use_fts: bool):
    from kartoteka_web.routes import cards

    statements: list[dict[str, object]] = []
    original_exec = session.exec

    def tracked_exec(statement, *args, **kwargs):
        result = original_exec(statement, *args, **kwargs)
        if getattr(statement, "is_select", False):
            return _TrackingResult(result, statement, statements)
        return result

    session.exec = tracked_exec
    original_fetch = cards._fetch_cardrecord_candidate_ids

    try:
        if not use_fts:
            with _override_attribute(cards, "_fetch_cardrecord_candidate_ids", lambda *a, **k: []):
                records, _total = cards._search_catalogue(
                    session,
                    query="Charizard",
                    name="Charizard",
                    limit=1,
                )
        else:
            records, _total = cards._search_catalogue(
                session,
                query="Charizard",
                name="Charizard",
                limit=1,
            )
    finally:
        session.exec = original_exec
        # Ensure the helper is restored even if the search failed early.
        cards._fetch_cardrecord_candidate_ids = original_fetch

    relevant = [
        entry
        for entry in statements
        if "from cardrecord" in str(entry["statement"]).lower()
    ]
    total_rows = sum(int(entry["rowcount"]) for entry in relevant)
    return records, len(relevant), total_rows


def test_card_search_uses_fts(monkeypatch, search_db):
    monkeypatch.setattr(
        "kartoteka_web.utils.images.cache_card_images", lambda payload, **_: payload
    )

    from kartoteka_web.routes import cards

    with Session(search_db.engine) as session:
        _seed_char_family(session)

        fallback_results, fallback_queries, fallback_rows = _run_search(
            session, use_fts=False
        )
        fts_results, fts_queries, fts_rows = _run_search(session, use_fts=True)

    assert [record.id for record in fts_results] == [record.id for record in fallback_results]
    assert fts_rows < fallback_rows
    assert fts_queries <= fallback_queries


def test_card_search_fuzzy_misspelling(monkeypatch, search_db):
    monkeypatch.setattr(
        "kartoteka_web.utils.images.cache_card_images", lambda payload, **_: payload
    )

    from kartoteka_web.routes import cards

    original_extract = cards.process.extract
    call_counter = {"count": 0}

    def tracking_extract(*args, **kwargs):
        call_counter["count"] += 1
        return original_extract(*args, **kwargs)

    monkeypatch.setattr(cards.process, "extract", tracking_extract)

    with Session(search_db.engine) as session:
        _seed_char_family(session)

        monkeypatch.setattr(cards, "_fetch_cardrecord_candidate_ids", lambda *a, **k: [])

        results, total_count = cards._search_catalogue(
            session,
            query="Sharizard",
            name="Sharizard",
            limit=5,
        )

    assert call_counter["count"] >= 1
    assert total_count >= 1
    assert results
    assert results[0].name == "Charizard"
    assert "Charizard" in {record.name for record in results}
