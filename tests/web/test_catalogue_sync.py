import sys
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine, select


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kartoteka_web import catalogue, models  # noqa: E402
from kartoteka_web.services import tcg_api  # noqa: E402


@pytest.fixture()
def in_memory_session(monkeypatch, tmp_path):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with engine.connect() as connection:
        connection.exec_driver_sql(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS cardrecord_search
            USING fts5(
                card_id UNINDEXED,
                name_normalized,
                set_name_normalized
            )
            """
        )

    marker_file = tmp_path / "marker.txt"
    progress_file = tmp_path / "progress.txt"

    monkeypatch.setattr(catalogue, "CATALOGUE_MARKER_FILE", marker_file)
    monkeypatch.setattr(catalogue, "CATALOGUE_PROGRESS_FILE", progress_file)
    monkeypatch.setattr(catalogue, "CATALOGUE_REQUEST_LIMIT", 3)
    monkeypatch.setattr(
        catalogue.image_utils, "cache_card_images", lambda payload, **_: payload
    )

    with Session(engine) as session:
        yield session


def test_refresh_catalogue_tracks_requests_and_markers(in_memory_session, monkeypatch):
    set_codes = ["alpha", "beta", "gamma"]
    monkeypatch.setattr(catalogue, "iter_known_set_codes", lambda: list(set_codes))

    set_infos = {
        "alpha": {"code": "alpha", "name": "Alpha", "total": 2, "era": "Test"},
        "beta": {"code": "beta", "name": "Beta", "total": 1, "era": "Test"},
        "gamma": {"code": "gamma", "name": "Gamma", "total": 1, "era": "Test"},
    }
    monkeypatch.setattr(
        catalogue.set_utils,
        "get_set_info",
        lambda set_code=None, set_name=None: set_infos.get(set_code)
        or set_infos.get(str(set_name or "").lower()),
    )

    payloads = {
        "alpha": (
            [
                {
                    "name": "Alpha One",
                    "number": "1",
                    "set_name": "Alpha",
                    "set_code": "alpha",
                },
                {
                    "name": "Alpha Two",
                    "number": "2",
                    "set_name": "Alpha",
                    "set_code": "alpha",
                },
            ],
            2,
        ),
        "beta": (
            [
                {
                    "name": "Beta Ace",
                    "number": "1",
                    "set_name": "Beta",
                    "set_code": "beta",
                }
            ],
            2,
        ),
        "gamma": (
            [
                {
                    "name": "Gamma Solo",
                    "number": "1",
                    "set_name": "Gamma",
                    "set_code": "gamma",
                }
            ],
            1,
        ),
    }

    call_order: list[str] = []

    def fake_list_set_cards(code, limit=0, **_kwargs):
        call_order.append(code)
        cards, request_count = payloads[code]
        return cards, request_count

    monkeypatch.setattr(tcg_api, "list_set_cards", fake_list_set_cards)

    events: list[tuple[str, dict]] = []

    def progress_hook(event: str, payload: dict):
        events.append((event, payload))

    total_changed = catalogue.refresh_catalogue(
        in_memory_session,
        now=catalogue.dt.datetime(2024, 1, 1, tzinfo=catalogue.dt.timezone.utc),
        force=True,
        progress=progress_hook,
    )

    assert call_order == ["alpha", "beta"]
    assert total_changed == 3

    records = in_memory_session.exec(select(models.CardRecord)).all()
    assert len(records) == 3

    # Limit event should reflect the aggregated request counter
    limit_events = [payload for name, payload in events if name == "limit"]
    assert limit_events and limit_events[0]["requests_used"] == 4

    complete_events = [payload for name, payload in events if name == "set.complete"]
    assert complete_events[0]["request_count"] == 2
    assert complete_events[0]["requests_used"] == 2
    assert complete_events[1]["request_count"] == 2
    assert complete_events[1]["requests_used"] == 4

    # Only progress marker should be written because the sync stopped at the limit
    assert catalogue.CATALOGUE_MARKER_FILE.exists() is False
    assert catalogue.CATALOGUE_PROGRESS_FILE.read_text(encoding="utf-8") == "beta"

