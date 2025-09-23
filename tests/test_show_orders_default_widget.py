import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent))
from ctk_mocks import DummyCTkButton, DummyCTkFrame, DummyCTkLabel  # noqa: E402


def test_open_valuation_history_populates_tree(monkeypatch):
    rows_inserted = []

    class DummyTree:
        def __init__(self, *_, **__):
            self._rows = []

        def heading(self, *_, **__):
            return None

        def column(self, *_, **__):
            return None

        def pack(self, *_, **__):
            return None

        def get_children(self):
            return list(range(len(self._rows)))

        def delete(self, item):
            idx = int(item)
            if 0 <= idx < len(self._rows):
                self._rows.pop(idx)

        def insert(self, *_args, values=None, **__):
            self._rows.append(tuple(values))
            rows_inserted.append(tuple(values))
            return len(self._rows) - 1

    sys.modules["customtkinter"] = SimpleNamespace(
        CTkFrame=DummyCTkFrame,
        CTkLabel=DummyCTkLabel,
        CTkButton=DummyCTkButton,
    )
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    import kartoteka.ui as ui
    importlib.reload(ui)

    monkeypatch.setattr(
        ui.csv_utils,
        "get_valuation_history",
        lambda: [
            {"date": "2024-12-30", "count": 2, "total": 50.0, "average": 25.0},
            {"date": "2024-12-31", "count": 1, "total": 30.0, "average": 30.0},
        ],
    )

    dummy_root = SimpleNamespace(
        minsize=lambda *a, **k: None,
        cget=lambda *a, **k: "white",
    )
    app = SimpleNamespace(
        root=dummy_root,
        create_button=lambda master, **kwargs: DummyCTkButton(master, **kwargs),
    )

    with patch.object(ui.ttk, "Treeview", DummyTree):
        ui.CardEditorApp.open_valuation_history(app)

    assert rows_inserted == [
        ("2024-12-30", 2, "50.00", "25.00"),
        ("2024-12-31", 1, "30.00", "30.00"),
    ]
    assert hasattr(app, "history_tree")
    assert callable(getattr(app, "refresh_history_view", None))
