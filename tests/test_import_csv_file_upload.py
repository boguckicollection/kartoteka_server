import csv

import kartoteka.csv_utils as csv_utils


def test_load_collection_export_by_product_code(tmp_path):
    path = tmp_path / "collection.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_utils.COLLECTION_FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerow(
            {
                "product_code": "PKM-SET-1",
                "name": "Pikachu",
                "number": "1",
                "set": "Base",
                "era": "Classic",
                "language": "ENG",
                "condition": "NM",
                "variant": "Common",
                "estimated_value": "10",
                "psa10_price": "100",
                "warehouse_code": "K1R1P1",
                "tags": "Common",
                "added_at": "2024-12-31",
            }
        )
    data = csv_utils.load_collection_export(str(path))
    assert data["PKM-SET-1"]["name"] == "Pikachu"


def test_load_collection_export_uses_warehouse_fallback(tmp_path):
    path = tmp_path / "collection.csv"
    headers = csv_utils.COLLECTION_FIELDNAMES
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter=";")
        writer.writeheader()
        row = dict.fromkeys(headers, "")
        row.update({"name": "Charmander", "warehouse_code": "K1R1P2"})
        writer.writerow(row)
    data = csv_utils.load_collection_export(str(path))
    assert data["K1R1P2"]["name"] == "Charmander"
