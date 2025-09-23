import csv
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui  # noqa: E402
import kartoteka.csv_utils as csv_utils  # noqa: E402


def _make_dummy_app(rows):
    app = SimpleNamespace(output_data=rows)
    app.back_to_welcome = lambda: None
    return app


def test_export_creates_collection_file(tmp_path, monkeypatch):
    collection_path = tmp_path / "collection.csv"
    warehouse_path = tmp_path / "magazyn.csv"
    monkeypatch.setenv("COLLECTION_EXPORT_CSV", str(collection_path))
    monkeypatch.setenv("WAREHOUSE_CSV", str(warehouse_path))
    import importlib
    importlib.reload(csv_utils)
    importlib.reload(ui)

    row = {
        "nazwa": "Pikachu",
        "numer": "001",
        "set": "Base",
        "era": "Classic",
        "język": "ENG",
        "stan": "NM",
        "product_code": "PKM-BASE-1",
        "cena": "12",
        "warehouse_code": "K1R1P1",
        "types": {"Common": True, "Holo": False, "Reverse": False},
    }

    with patch("tkinter.messagebox.showinfo"):
        ui.CardEditorApp.export_csv(_make_dummy_app([row]))

    with collection_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        assert reader.fieldnames == csv_utils.COLLECTION_FIELDNAMES
        data = next(reader)
    assert data["name"] == "Pikachu"
    assert data["number"] == "1"
    assert data["variant"] == "Common"
    assert data["language"] == "ENG"
    assert data["condition"] == "NM"
    assert data["estimated_value"] == "12"
    assert data["warehouse_code"] == "K1R1P1"
    assert data["tags"] == "Common"


def test_export_overwrites_existing_product_code(tmp_path, monkeypatch):
    collection_path = tmp_path / "collection.csv"
    warehouse_path = tmp_path / "magazyn.csv"
    monkeypatch.setenv("COLLECTION_EXPORT_CSV", str(collection_path))
    monkeypatch.setenv("WAREHOUSE_CSV", str(warehouse_path))
    import importlib
    importlib.reload(csv_utils)
    importlib.reload(ui)

    with collection_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=csv_utils.COLLECTION_FIELDNAMES, delimiter=";"
        )
        writer.writeheader()
        writer.writerow(
            {
                "product_code": "PKM-BASE-1",
                "name": "Old",
                "number": "1",
                "set": "Base",
                "era": "Classic",
                "language": "ENG",
                "condition": "NM",
                "variant": "Common",
                "estimated_value": "5",
                "psa10_price": "",
                "warehouse_code": "K1R1P1",
                "tags": "Common",
                "added_at": "2024-12-30",
            }
        )

    new_row = {
        "nazwa": "Pikachu",
        "numer": "1",
        "set": "Base",
        "era": "Classic",
        "język": "ENG",
        "stan": "LP",
        "product_code": "PKM-BASE-1",
        "cena": "15",
        "warehouse_code": "K1R1P1",
    }

    with patch("tkinter.messagebox.showinfo"):
        ui.CardEditorApp.export_csv(_make_dummy_app([new_row]))

    with collection_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        data = {row["product_code"]: row for row in reader}
    assert data["PKM-BASE-1"]["estimated_value"] == "15"
    assert data["PKM-BASE-1"]["condition"] == "LP"


def test_export_updates_warehouse_file(tmp_path, monkeypatch):
    collection_path = tmp_path / "collection.csv"
    warehouse_path = tmp_path / "magazyn.csv"
    monkeypatch.setenv("COLLECTION_EXPORT_CSV", str(collection_path))
    monkeypatch.setenv("WAREHOUSE_CSV", str(warehouse_path))
    import importlib
    importlib.reload(csv_utils)
    importlib.reload(ui)

    row = {
        "nazwa": "Eevee",
        "numer": "2",
        "set": "Jungle",
        "era": "Classic",
        "język": "ENG",
        "stan": "NM",
        "product_code": "PKM-JUN-2",
        "cena": "8",
        "warehouse_code": "K1R1P2",
    }

    with patch("tkinter.messagebox.showinfo"):
        ui.CardEditorApp.export_csv(_make_dummy_app([row]))

    with warehouse_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        stored = next(reader)
    assert stored["name"] == "Eevee"
    assert stored["number"] == "2"
    assert stored["set"] == "Jungle"
    assert stored["price"] == "8"
    assert stored["variant"] == "common"
