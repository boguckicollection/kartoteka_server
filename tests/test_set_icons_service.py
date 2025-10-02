from __future__ import annotations

import asyncio
from pathlib import Path

import anyio

from kartoteka_web.services import set_icons


class DummyResponse:
    def __init__(self, *, status_code: int = 200, json_data=None, content: bytes = b""):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON payload present")
        return self._json_data


class DummySession:
    def __init__(self, responses: dict[str, list[DummyResponse]]):
        self._responses = responses
        self.headers: dict[str, str] = {}
        self.requested: list[str] = []

    def get(self, url: str, timeout: float | None = None):  # noqa: D401 - mimic requests
        self.requested.append(url)
        try:
            queue = self._responses[url]
        except KeyError as exc:  # pragma: no cover - guard for misconfigured tests
            raise AssertionError(f"Unexpected URL requested: {url}") from exc
        if not queue:
            raise AssertionError(f"No more responses available for {url}")
        return queue.pop(0)


def _session_with_set_payload(set_payloads: list[dict[str, object]], *, symbol_responses):
    responses: dict[str, list[DummyResponse]] = {
        set_icons.SET_LIST_URL: [
            DummyResponse(json_data={"data": set_payloads}),
        ]
    }
    responses.update(symbol_responses)
    return DummySession(responses)


def test_set_icons_downloads_missing_symbols(tmp_path: Path):
    symbol_url = "https://img.example/swsh1.png"
    session = _session_with_set_payload(
        [
            {"id": "swsh1", "images": {"symbol": symbol_url}},
            {"id": "Missing", "images": {}},
            {"name": "Promo Collection"},
        ],
        symbol_responses={
            symbol_url: [DummyResponse(content=b"fake-bytes")],
        },
    )

    saved = set_icons.ensure_set_icons(
        icons_directory=tmp_path,
        session=session,
    )

    expected_path = tmp_path / "swsh1.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"fake-bytes"
    assert saved == [expected_path]

    # Ensure a clean code was derived for the entry with only a name.
    assert not (tmp_path / "promocollection.png").exists()


def test_set_icons_skips_existing_files_without_force(tmp_path: Path):
    existing_path = tmp_path / "base1.png"
    existing_path.write_bytes(b"original")

    symbol_url = "https://img.example/base1.png"
    another_symbol_url = "https://img.example/base2.png"
    session = _session_with_set_payload(
        [
            {"id": "base1", "images": {"symbol": symbol_url}},
            {"id": "base2", "images": {"symbol": another_symbol_url}},
        ],
        symbol_responses={
            another_symbol_url: [DummyResponse(content=b"new")],
        },
    )

    saved = set_icons.ensure_set_icons(
        icons_directory=tmp_path,
        session=session,
        force=False,
    )

    assert existing_path.read_bytes() == b"original"
    assert saved == [tmp_path / "base2.png"]
    assert session.requested.count(symbol_url) == 0
    assert session.requested.count(another_symbol_url) == 1


def test_set_icons_force_overwrites_existing(tmp_path: Path):
    existing_path = tmp_path / "svpblackstar.png"
    existing_path.write_bytes(b"old")

    set_payload = {
        "name": "SVP Black Star",
        "images": {"symbol": "https://img.example/svp.png"},
    }
    session = _session_with_set_payload(
        [set_payload],
        symbol_responses={
            "https://img.example/svp.png": [DummyResponse(content=b"updated")],
        },
    )

    saved = set_icons.ensure_set_icons(
        icons_directory=tmp_path,
        session=session,
        force=True,
    )

    assert existing_path.read_bytes() == b"updated"
    assert saved == [existing_path]


def test_set_icons_thread_invocation_matches_results(tmp_path: Path):
    symbol_url = "https://img.example/swsh1.png"

    def build_session() -> DummySession:
        return _session_with_set_payload(
            [
                {"id": "swsh1", "images": {"symbol": symbol_url}},
            ],
            symbol_responses={
                symbol_url: [DummyResponse(content=b"threaded")],
            },
        )

    direct_dir = tmp_path / "direct"
    thread_dir = tmp_path / "thread"
    direct_dir.mkdir()
    thread_dir.mkdir()

    direct_saved = set_icons.ensure_set_icons(
        icons_directory=direct_dir,
        session=build_session(),
    )

    async def run_in_thread() -> list[Path]:
        return await anyio.to_thread.run_sync(
            lambda: set_icons.ensure_set_icons(
                icons_directory=thread_dir,
                session=build_session(),
            )
        )

    threaded_saved = asyncio.run(run_in_thread())

    assert [path.name for path in threaded_saved] == [path.name for path in direct_saved]
    for path in threaded_saved:
        assert path.read_bytes() == b"threaded"


def test_set_icons_closes_created_session(monkeypatch, tmp_path: Path):
    class CloseTrackingSession(DummySession):
        def __init__(self):
            super().__init__(
                {
                    set_icons.SET_LIST_URL: [DummyResponse(json_data={"data": []})],
                }
            )
            self.closed = False

        def close(self):
            self.closed = True

    session = CloseTrackingSession()
    monkeypatch.setattr(set_icons, "_build_retrying_session", lambda: session)

    set_icons.ensure_set_icons(icons_directory=tmp_path)

    assert session.closed is True


def test_extract_clean_code_prefers_code_over_id():
    payload = {
        "id": "special-set",
        "code": "base1",
    }

    assert set_icons._extract_clean_code(payload) == "base1"

