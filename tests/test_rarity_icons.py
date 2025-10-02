from __future__ import annotations

from pathlib import Path

EXPECTED_RARITY_ICONS = {
    "common": {
        "asset_path": Path("icon/rarity/Rarity_Common.png"),
        "snippet": '"common": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Common.png`',
    },
    "uncommon": {
        "asset_path": Path("icon/rarity/Rarity_Uncommon.png"),
        "snippet": '"uncommon": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Uncommon.png`',
    },
    "rare": {
        "asset_path": Path("icon/rarity/Rarity_Rare.png"),
        "snippet": '"rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Rare.png`',
    },
    "double-rare": {
        "asset_path": Path("icon/rarity/Rarity_Double_Rare.png"),
        "snippet": '"double-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Double_Rare.png`',
    },
    "ultra-rare": {
        "asset_path": Path("icon/rarity/Rarity_Ultra_Rare.png"),
        "snippet": '"ultra-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Ultra_Rare.png`',
    },
    "hyper-rare": {
        "asset_path": Path("icon/rarity/Rarity_Hyper_Rare.png"),
        "snippet": '"hyper-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Hyper_Rare.png`',
    },
    "illustration-rare": {
        "asset_path": Path("icon/rarity/Rarity_Illustration Rare.png"),
        "snippet": '"illustration-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Illustration%20Rare.png`',
    },
    "special-illustration-rare": {
        "asset_path": Path("icon/rarity/Rarity_Special_Illustration_Rare.png"),
        "snippet": '"special-illustration-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Special_Illustration_Rare.png`',
    },
    "shiny-rare": {
        "asset_path": Path("icon/rarity/Rarity_Shiny_Rare.png"),
        "snippet": '"shiny-rare": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_Shiny_Rare.png`',
    },
    "ace-spec": {
        "asset_path": Path("icon/rarity/Rarity_ACE_SPEC_Rare.png"),
        "snippet": '"ace-spec": `${RARITY_ICON_IMAGE_BASE_PATH}/Rarity_ACE_SPEC_Rare.png`',
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
