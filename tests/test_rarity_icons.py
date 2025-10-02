from __future__ import annotations

from pathlib import Path

EXPECTED_RARITY_ICONS = {
    "common": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/common.svg"),
        "snippet": '"common": `${RARITY_ICON_BASE_PATH}/common.svg`',
    },
    "uncommon": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/uncommon.svg"),
        "snippet": '"uncommon": `${RARITY_ICON_BASE_PATH}/uncommon.svg`',
    },
    "rare": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare.svg"),
        "snippet": '"rare": `${RARITY_ICON_BASE_PATH}/rare.svg`',
    },
    "rare-holo": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare-holo.svg"),
        "snippet": '"rare-holo": `${RARITY_ICON_BASE_PATH}/rare-holo.svg`',
    },
    "rare-ultra": {
        "asset_path": Path("icon/rarity/Rarity_Ultra_Rare.png"),
        "snippet": '"rare-ultra": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png`',
    },
    "ultra-rare": {
        "asset_path": Path("icon/rarity/Rarity_Ultra_Rare.png"),
        "snippet": '"ultra-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png`',
    },
    "rare-double": {
        "asset_path": Path("icon/rarity/Rarity_Double_Rare.png"),
        "snippet": '"rare-double": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png`',
    },
    "double-rare": {
        "asset_path": Path("icon/rarity/Rarity_Double_Rare.png"),
        "snippet": '"double-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png`',
    },
    "rare-secret": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare-secret.svg"),
        "snippet": '"rare-secret": `${RARITY_ICON_BASE_PATH}/rare-secret.svg`',
    },
    "rare-shiny": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare-shiny.svg"),
        "snippet": '"rare-shiny": `${RARITY_ICON_BASE_PATH}/rare-shiny.svg`',
    },
    "rare-ace": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare-ace.svg"),
        "snippet": '"rare-ace": `${RARITY_ICON_BASE_PATH}/rare-ace.svg`',
    },
    "rare-illustration": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare-illustration.svg"),
        "snippet": '"rare-illustration": `${RARITY_ICON_BASE_PATH}/rare-illustration.svg`',
    },
    "promo": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/promo.svg"),
        "snippet": '"promo": `${RARITY_ICON_BASE_PATH}/promo.svg`',
    },
    "rare-rainbow": {
        "asset_path": Path("kartoteka_web/static/icons/rarity/rare-rainbow.svg"),
        "snippet": '"rare-rainbow": `${RARITY_ICON_BASE_PATH}/rare-rainbow.svg`',
    },
}


def test_rarity_icon_assets_exist():
    missing_assets = {
        details["asset_path"]
        for details in EXPECTED_RARITY_ICONS.values()
        if not details["asset_path"].is_file()
    }
    assert not missing_assets, f"Brakuje plików ikon: {[str(path) for path in sorted(missing_assets)]}"


def test_rarity_icon_map_contains_expected_entries():
    js_path = Path("kartoteka_web/static/js/app.js")
    content = js_path.read_text(encoding="utf-8")
    for key, details in EXPECTED_RARITY_ICONS.items():
        assert details["snippet"] in content, f"Nie znaleziono mapowania dla rzadkości '{key}'"
