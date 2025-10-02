"""Regression coverage for canonical set icon resolution."""

from __future__ import annotations

from pathlib import Path

from kartoteka_web.utils.sets import resolve_cached_set_icon


def test_resolve_cached_set_icon_with_canonical_mapping(tmp_path: Path) -> None:
    """Candidates with alternative codes should resolve to canonical slugs."""

    icon_directory = tmp_path / "set-icons"
    icon_directory.mkdir()
    (icon_directory / "sv01.png").write_bytes(b"fake icon contents")

    slug, url = resolve_cached_set_icon(
        set_code="SV",
        set_name="Scarlet & Violet",
        icons_directory=icon_directory,
    )

    assert slug == "sv01"
    assert url == "/icon/set/sv01.png"
