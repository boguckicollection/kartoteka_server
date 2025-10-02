from __future__ import annotations

from pathlib import Path

import re

EXPECTED_RARITY_ICONS = {
    "common": "common.svg",
    "uncommon": "uncommon.svg",
    "rare": "rare.svg",
    "rare-holo": "rare-holo.svg",
    "rare-ultra": "rare-ultra.svg",
    "rare-secret": "rare-secret.svg",
    "rare-shiny": "rare-shiny.svg",
    "rare-ace": "rare-ace.svg",
    "rare-illustration": "rare-illustration.svg",
    "promo": "promo.svg",
    "rare-rainbow": "rare-rainbow.svg",
}


def test_rarity_icon_assets_exist():
    base_path = Path("kartoteka_web/static/icons/rarity")
    assert base_path.is_dir(), "Brakuje katalogu z ikonami rzadkości"
    missing = [name for name in EXPECTED_RARITY_ICONS.values() if not (base_path / name).is_file()]
    assert not missing, f"Brakuje plików ikon: {missing}"


def test_rarity_icon_map_contains_expected_entries():
    js_path = Path("kartoteka_web/static/js/app.js")
    content = js_path.read_text(encoding="utf-8")
    for key, filename in EXPECTED_RARITY_ICONS.items():
        pattern = re.escape(f'"{key}": `${{RARITY_ICON_BASE_PATH}}/{filename}`')
        assert re.search(pattern, content), f"Nie znaleziono mapowania dla rzadkości '{key}'"
