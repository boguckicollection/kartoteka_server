from datetime import date

import kartoteka.csv_utils as csv_utils


def test_format_collection_row_uses_types_dict():
    row = {
        "nazwa": "Pikachu",
        "numer": "001",
        "set": "Base",
        "era": "Classic",
        "język": "ENG",
        "stan": "NM",
        "types": {"Common": False, "Holo": True, "Reverse": False},
        "cena": "15",
        "warehouse_code": "K1R1P1",
        "product_code": "PKM-BASE-1",
    }
    result = csv_utils.format_collection_row(row)
    assert result["variant"] == "Holo"
    assert result["tags"] == "Holo"


def test_format_collection_row_defaults_added_at():
    today = date.today().isoformat()
    row = {
        "nazwa": "Charmander",
        "numer": "4",
        "set": "Base",
        "era": "Classic",
        "język": "ENG",
        "stan": "LP",
        "typ": "Reverse",
        "cena": "7",
        "warehouse_code": "K1R1P2",
        "product_code": "PKM-BASE-4R",
    }
    result = csv_utils.format_collection_row(row)
    assert result["added_at"] == today
    assert result["variant"] == "Reverse"
    assert result["tags"] == "Reverse"
