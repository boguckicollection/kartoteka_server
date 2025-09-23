from . import csv_utils

__all__ = ["CardEditorApp", "csv_utils"]


def __getattr__(name: str):
    if name == "CardEditorApp":
        from .ui import CardEditorApp  # noqa: WPS433 - lazy import

        return CardEditorApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
