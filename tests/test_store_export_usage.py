import csv
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import tkinter as tk
import importlib

# provide minimal customtkinter stub before importing modules
sys.modules["customtkinter"] = SimpleNamespace(
    CTkEntry=tk.Entry,
    CTkImage=MagicMock(),
    CTkButton=MagicMock,
    CTkToplevel=MagicMock,
)

sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui
import kartoteka.csv_utils as csv_utils
importlib.reload(ui)
importlib.reload(csv_utils)


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _create_collection_csv(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=csv_utils.COLLECTION_FIELDNAMES, delimiter=";"
        )
        writer.writeheader()
        writer.writerow(
            {
                "product_code": "PKM-PAL-1",
                "name": "Pikachu",
                "number": "1",
                "set": "Paldea Evolved",
                "era": "EraX",
                "language": "ENG",
                "condition": "NM",
                "variant": "Common",
                "estimated_value": "99",
                "psa10_price": "",
                "warehouse_code": "K1R1P1",
                "tags": "Common",
                "added_at": "2024-12-31",
            }
        )


def test_load_collection_export(tmp_path):
    csv_path = tmp_path / "collection.csv"
    _create_collection_csv(csv_path)
    data = csv_utils.load_collection_export(str(csv_path))
    assert "PKM-PAL-1" in data
    assert data["PKM-PAL-1"]["estimated_value"] == "99"


def test_analyze_and_fill_uses_collection_export(monkeypatch, tmp_path):
    csv_path = tmp_path / "collection.csv"
    _create_collection_csv(csv_path)
    collection_data = csv_utils.load_collection_export(str(csv_path))

    name_entry = MagicMock()
    num_entry = MagicMock()
    set_var = DummyVar("")
    era_var = DummyVar("")
    price_entry = MagicMock()
    for entry in (name_entry, num_entry, price_entry):
        entry.delete = MagicMock()
        entry.insert = MagicMock()

    dummy = SimpleNamespace(
        root=SimpleNamespace(after=lambda delay, func: func()),
        entries={
            "nazwa": name_entry,
            "numer": num_entry,
            "set": set_var,
            "era": era_var,
            "cena": price_entry,
        },
        index=0,
        update_set_options=lambda: None,
        update_set_area_preview=lambda *a, **k: None,
        collection_data=collection_data,
        hash_db=None,
        auto_lookup=False,
    )
    dummy._apply_analysis_result = ui.CardEditorApp._apply_analysis_result.__get__(dummy, ui.CardEditorApp)

    monkeypatch.setattr(
        ui,
        "analyze_card_image",
        lambda *a, **k: {"name": "Pikachu", "number": "1", "set": "Paldea Evolved"},
    )

    ui.CardEditorApp._analyze_and_fill(dummy, "x", 0)
    assert era_var.value == "EraX"
    price_entry.insert.assert_called_with(0, "99")
