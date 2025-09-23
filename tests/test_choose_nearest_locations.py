from pathlib import Path

import kartoteka.csv_utils as csv_utils


def test_get_valuation_history_groups_by_day(tmp_path):
    warehouse = tmp_path / "magazyn.csv"
    warehouse.write_text(
        "name;number;set;warehouse_code;price;image;variant;sold;added_at\n"
        "A;1;Set1;K1R1P1;10;;common;;2024-12-30T10:00:00\n"
        "B;2;Set1;K1R1P2;5;;common;;2024-12-30T11:00:00\n"
        "C;3;Set2;K1R1P3;12;;common;;2024-12-31T09:00:00\n",
        encoding="utf-8",
    )
    result = csv_utils.get_valuation_history(str(warehouse))
    assert result == [
        {"date": "2024-12-31", "count": 1, "total": 12.0, "average": 12.0},
        {"date": "2024-12-30", "count": 2, "total": 15.0, "average": 7.5},
    ]


def test_get_valuation_history_honours_limit(tmp_path):
    warehouse = tmp_path / "magazyn.csv"
    rows = [
        "name;number;set;warehouse_code;price;image;variant;sold;added_at\n",
    ]
    for idx in range(5):
        day = f"2025-01-0{idx+1}"
        rows.append(f"A;{idx};Set;K1R1P{idx};{idx + 1};;;{''};{day}T08:00:00\n")
    warehouse.write_text("".join(rows), encoding="utf-8")
    result = csv_utils.get_valuation_history(str(warehouse), limit=2)
    assert len(result) == 2
    assert result[0]["date"] == "2025-01-05"
    assert result[1]["date"] == "2025-01-04"
