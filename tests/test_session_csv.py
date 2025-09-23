import csv
import sys
from pathlib import Path
from types import SimpleNamespace
import csv
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui
import kartoteka.csv_utils as csv_utils


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def make_dummy():
    return SimpleNamespace(
        entries={
            "nazwa": DummyVar("Charizard"),
            "numer": DummyVar("4"),
            "set": DummyVar("Base"),
            "era": DummyVar(""),
            "język": DummyVar("ENG"),
            "stan": DummyVar("NM"),
            "cena": DummyVar(""),
            "psa10_price": DummyVar("")
        },
        type_vars={"Reverse": DummyVar(False), "Holo": DummyVar(False)},
        card_cache={},
        cards=["/tmp/char.jpg"],
        index=0,
        folder_name="folder",
        file_to_key={},
        product_code_map={},
        next_free_location=lambda: "K1R1P1",
        generate_location=lambda idx: "K1R1P1",
        output_data=[None],
        get_price_from_db=lambda *a: None,
        fetch_card_price=lambda *a: None,
        fetch_psa10_price=lambda *a, **k: "",
    )


def test_session_csv_created(tmp_path):
    session_path = tmp_path / "session.csv"
    dummy = SimpleNamespace(
        start_box_var=DummyVar("1"),
        start_col_var=DummyVar("1"),
        start_pos_var=DummyVar("1"),
        scan_folder_var=DummyVar("folder"),
        load_images=lambda self, folder: None,
    )

    with patch.object(ui.CardEditorApp, "load_images", lambda self, folder: None), \
         patch("tkinter.filedialog.asksaveasfilename", return_value=str(session_path)):
        ui.CardEditorApp.browse_scans(dummy)

    assert dummy.session_csv_path == str(session_path)
    with open(session_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        assert reader.fieldnames == csv_utils.COLLECTION_FIELDNAMES
        assert "estimated_value" in reader.fieldnames


def test_save_current_appends_session(tmp_path):
    session_path = tmp_path / "session.csv"
    dummy = make_dummy()
    dummy.session_csv_path = str(session_path)
    with open(session_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=csv_utils.COLLECTION_FIELDNAMES, delimiter=";"
        )
        writer.writeheader()

    ui.CardEditorApp.save_current_data(dummy)

    with open(session_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "Charizard"
        assert rows[0]["number"] == "4"
        assert rows[0]["language"] == "ENG"
        assert rows[0]["condition"] == "NM"
        assert rows[0]["variant"] == "Common"


def test_export_accumulates_between_sessions(tmp_path, monkeypatch):
    out_path = tmp_path / "collection.csv"
    inv_path = tmp_path / "inv.csv"
    monkeypatch.setenv("COLLECTION_EXPORT_CSV", str(out_path))
    monkeypatch.setenv("WAREHOUSE_CSV", str(inv_path))
    import importlib
    importlib.reload(csv_utils)
    importlib.reload(ui)

    base_row = {
        "nazwa": "Pikachu",
        "numer": "1",
        "set": "Base",
        "era": "Era1",
        "product_code": "PC1",
        "cena": "10",
    }
    second_row = {
        "nazwa": "Charmander",
        "numer": "2",
        "set": "Base",
        "era": "Era1",
        "product_code": "PC2",
        "cena": "5",
    }

    dummy1 = SimpleNamespace(output_data=[base_row], back_to_welcome=lambda: None)
    dummy2 = SimpleNamespace(output_data=[dict(base_row), second_row], back_to_welcome=lambda: None)

    with patch("tkinter.messagebox.showinfo"):
        ui.CardEditorApp.export_csv(dummy1)
        ui.CardEditorApp.export_csv(dummy2)

    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = {r["product_code"]: r for r in reader}
        assert set(rows) == {"PC1", "PC2"}
        assert rows["PC1"]["estimated_value"] == "10"
        assert rows["PC2"]["estimated_value"] == "5"

