import os
import re
import csv
from datetime import date, timedelta
from typing import Iterable, Optional, Tuple
from tkinter import filedialog, messagebox, TclError

import logging

logger = logging.getLogger(__name__)

INVENTORY_CSV = os.getenv(
    "INVENTORY_CSV", os.getenv("WAREHOUSE_CSV", "magazyn.csv")
)
WAREHOUSE_CSV = os.getenv("WAREHOUSE_CSV", INVENTORY_CSV)
COLLECTION_EXPORT_CSV = os.getenv("COLLECTION_EXPORT_CSV") or os.getenv(
    "STORE_EXPORT_CSV", "collection_export.csv"
)

# Track last modification time and cached statistics for the warehouse CSV
WAREHOUSE_CSV_MTIME: Optional[float] = None
_inventory_stats_cache: Optional[Tuple[int, float, int, float]] = None
_inventory_stats_path: Optional[str] = None

# column order for exported collection CSV files
COLLECTION_FIELDNAMES = [
    "product_code",
    "name",
    "number",
    "set",
    "era",
    "language",
    "condition",
    "variant",
    "estimated_value",
    "psa10_price",
    "warehouse_code",
    "tags",
    "added_at",
]

# include a ``sold`` flag so individual cards can be marked as sold and track
# when cards were added to the warehouse
WAREHOUSE_FIELDNAMES = [
    "name",
    "number",
    "set",
    "warehouse_code",
    "price",
    "image",
    "variant",
    "sold",
    "added_at",
]


def _ensure_default_warehouse_csv(path: str = WAREHOUSE_CSV) -> None:
    """Ensure a warehouse CSV with the correct header exists."""

    if not path:
        return
    if os.path.exists(path):
        return
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=WAREHOUSE_FIELDNAMES, delimiter=";")
            writer.writeheader()
    except OSError:
        logger.debug("Unable to create default warehouse CSV at %s", path)


_ensure_default_warehouse_csv()


def load_collection_export(path: str = COLLECTION_EXPORT_CSV) -> dict[str, dict[str, str]]:
    """Return mapping of ``product_code`` to rows from the collection CSV.

    Parameters
    ----------
    path:
        Optional path to the collection CSV.  Defaults to
        :data:`COLLECTION_EXPORT_CSV`.

    Returns
    -------
    dict[str, dict[str, str]]
        Mapping keyed by product code.  Missing files result in an empty
        mapping.
    """

    data: dict[str, dict[str, str]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                code = (row.get("product_code") or "").strip()
                if not code:
                    code = (row.get("warehouse_code") or "").strip()
                if code:
                    data[code] = row
    except OSError:
        return {}
    return data


# Backwards compatibility for modules still importing the legacy helper
load_store_export = load_collection_export


def _sanitize_number(value: str) -> str:
    """Return ``value`` without leading zeros.

    Parameters
    ----------
    value:
        Raw number string.

    Returns
    -------
    str
        Normalised number or ``"0"`` if the result is empty.
    """

    return value.strip().lstrip("0") or "0"


VARIANT_SUFFIXES = {"holo": "H", "reverse": "R"}


def build_product_code(set_name: str, number: str, variant: str | None = None) -> str:
    """Return a product code based on set abbreviation and card number."""
    from .ui import get_set_abbr  # local import to avoid circular dependency

    abbr = get_set_abbr(set_name)
    if not abbr:
        sanitized = re.sub(r"[^A-Za-z0-9]", "", set_name).upper()
        abbr = sanitized[:3]
    num = _sanitize_number(str(number))
    suffix = VARIANT_SUFFIXES.get((variant or "").strip().lower(), "")
    return f"PKM-{abbr}-{num}{suffix}"


def find_duplicates(
    name: str, number: str, set_name: str, variant: str | None = None
):
    """Return rows from ``WAREHOUSE_CSV`` matching the given card details.

    Parameters
    ----------
    name, number, set_name:
        Card attributes to match against ``WAREHOUSE_CSV`` entries.
    variant:
        Optional card variant. When ``None`` or falsy any variant matches.

    Returns
    -------
    list[dict[str, str]]
        List of matching rows including warehouse codes.
    """

    from .ui import normalize  # local import to avoid circular dependency

    matches = []
    number = _sanitize_number(str(number))
    name_norm = normalize(name)
    set_norm = normalize(set_name)
    variant_norm = normalize(variant) if variant else None

    if not os.path.exists(WAREHOUSE_CSV):
        return matches

    try:
        with open(WAREHOUSE_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                row_number = _sanitize_number(str(row.get("number", "")))
                row_name = normalize(row.get("name") or "")
                row_set = normalize(row.get("set") or "")
                row_variant = normalize(row.get("variant") or "common") or "common"
                if (
                    row_name == name_norm
                    and row_number == number
                    and row_set == set_norm
                    and (variant_norm is None or row_variant == variant_norm)
                ):
                    matches.append(row)
    except OSError:
        pass

    return matches


def get_row_by_code(code: str, path: str = WAREHOUSE_CSV) -> Optional[dict[str, str]]:
    """Return the first row in ``path`` matching ``code``.

    Parameters
    ----------
    code:
        Warehouse code identifying a card.
    path:
        Optional path to the warehouse CSV. Defaults to :data:`WAREHOUSE_CSV`.

    Returns
    -------
    dict | None
        Matching row or ``None`` when the code is not found or the file is
        inaccessible.
    """

    code = (code or "").strip()
    if not code:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                codes = [c.strip() for c in str(row.get("warehouse_code") or "").split(";") if c.strip()]
                if code in codes:
                    return row
    except OSError:
        return None
    return None


def mark_codes_as_sold(codes: Iterable[str], path: Optional[str] = None) -> int:
    """Mark the provided warehouse codes as sold in ``path``.

    Parameters
    ----------
    codes:
        Iterable of warehouse codes to mark as sold. Empty strings are ignored.
    path:
        Optional path to the warehouse CSV. Defaults to :data:`WAREHOUSE_CSV`.

    Returns
    -------
    int
        Number of rows updated.
    """

    normalized = {c.strip() for c in codes if c and c.strip()}
    if not normalized:
        return 0

    if path is None:
        path = WAREHOUSE_CSV

    try:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            fieldnames = reader.fieldnames or WAREHOUSE_FIELDNAMES
            rows = list(reader)
    except OSError:
        return 0

    updated = 0
    for row in rows:
        row_codes = {
            code.strip()
            for code in str(row.get("warehouse_code") or "").split(";")
            if code.strip()
        }
        if row_codes and row_codes.intersection(normalized):
            if str(row.get("sold") or "").strip().lower() not in {"1", "true", "yes"}:
                row["sold"] = "1"
                updated += 1

    if not updated:
        return 0

    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        return 0

    try:
        get_inventory_stats(path, force=True)
    except Exception:
        pass
    return updated


def get_inventory_stats(path: str = WAREHOUSE_CSV, force: bool = False):
    """Return statistics for both unsold and sold items in the warehouse CSV.

    Parameters
    ----------
    path:
        Optional path to the warehouse CSV. Defaults to ``WAREHOUSE_CSV``.

    Returns
    -------
    tuple[int, float, int, float]
        ``(count_unsold, total_unsold, count_sold, total_sold)`` where each
        count is the number of rows and each total is the sum of the ``price``
        column for items in the respective category.
    """

    count_unsold = 0
    total_unsold = 0.0
    count_sold = 0
    total_sold = 0.0

    global WAREHOUSE_CSV_MTIME, _inventory_stats_cache, _inventory_stats_path

    # Determine current modification time if the file exists
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        current_mtime = None

    cache_valid = (
        not force
        and _inventory_stats_cache is not None
        and _inventory_stats_path == path
        and WAREHOUSE_CSV_MTIME == current_mtime
    )

    if cache_valid:
        return _inventory_stats_cache

    if not os.path.exists(path):
        _inventory_stats_cache = (
            count_unsold,
            total_unsold,
            count_sold,
            total_sold,
        )
        _inventory_stats_path = path
        WAREHOUSE_CSV_MTIME = current_mtime
        return _inventory_stats_cache

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            sold_flag = str(row.get("sold") or "").lower() in {"1", "true", "yes"}
            price_raw = str(row.get("price") or "0").replace(",", ".")
            try:
                price = float(price_raw)
            except ValueError:
                continue

            if sold_flag:
                count_sold += 1
                total_sold += price
            else:
                count_unsold += 1
                total_unsold += price

    _inventory_stats_cache = (
        count_unsold,
        total_unsold,
        count_sold,
        total_sold,
    )
    _inventory_stats_path = path
    WAREHOUSE_CSV_MTIME = current_mtime
    return _inventory_stats_cache


def get_daily_additions(days: int = 7) -> dict[str, int]:
    """Return counts of cards added per day for the last ``days`` days."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    counts = {
        (start + timedelta(days=i)).isoformat(): 0 for i in range(days)
    }
    if not os.path.exists(WAREHOUSE_CSV):
        return counts

    with open(WAREHOUSE_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            added_raw = (row.get("added_at") or "").split("T", 1)[0]
            try:
                added_date = date.fromisoformat(added_raw)
            except ValueError:
                continue
            if start <= added_date <= end:
                counts[added_date.isoformat()] += 1
    return counts


def get_valuation_history(
    path: str = WAREHOUSE_CSV, limit: Optional[int] = None
) -> list[dict[str, object]]:
    """Return aggregated valuation history grouped by day."""

    if not os.path.exists(path):
        return []

    history: dict[str, dict[str, object]] = {}

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            added_raw = (row.get("added_at") or "").split("T", 1)[0]
            try:
                day = date.fromisoformat(added_raw)
            except ValueError:
                continue
            try:
                price = float(row.get("price") or 0)
            except (TypeError, ValueError):
                price = 0.0
            entry = history.setdefault(
                day.isoformat(), {"date": day.isoformat(), "count": 0, "total": 0.0}
            )
            entry["count"] = int(entry["count"]) + 1
            entry["total"] = float(entry["total"]) + price

    entries = sorted(history.values(), key=lambda item: item["date"], reverse=True)
    if limit is not None:
        entries = entries[:limit]

    for entry in entries:
        total = float(entry["total"])
        count = int(entry["count"])
        entry["total"] = round(total, 2)
        entry["average"] = round(total / count, 2) if count else 0.0

    return entries


def format_collection_row(row: dict[str, object]) -> dict[str, str]:
    """Return a row formatted for the collection CSV."""

    types = row.get("types") or {}
    if isinstance(types, dict):
        selected = [name for name, value in types.items() if value]
    else:
        selected = []

    variant = row.get("variant") or row.get("typ") or ""
    if not variant:
        if "Holo" in selected:
            variant = "Holo"
        elif "Reverse" in selected:
            variant = "Reverse"
        else:
            variant = "Common"

    number = _sanitize_number(str(row.get("numer", "")))
    added_at = row.get("added_at") or date.today().isoformat()

    tags = row.get("typ")
    if not tags and selected:
        tags = ", ".join(selected)

    return {
        "product_code": str(row.get("product_code", "")),
        "name": str(row.get("nazwa", "")),
        "number": number,
        "set": str(row.get("set", "")),
        "era": str(row.get("era", "")),
        "language": str(row.get("język", "")),
        "condition": str(row.get("stan", "")),
        "variant": str(variant),
        "estimated_value": str(row.get("cena", "")),
        "psa10_price": str(row.get("psa10_price", "")),
        "warehouse_code": str(row.get("warehouse_code", "")),
        "tags": str(tags or ""),
        "added_at": str(added_at),
    }


def format_warehouse_row(row):
    """Return a row formatted for the warehouse CSV."""
    types = row.get("types") or {}
    variant = (
        "holo"
        if types.get("Holo")
        else "reverse"
        if types.get("Reverse")
        else row.get("variant", "common")
    )
    return {
        "name": row.get("nazwa", ""),
        "number": row.get("numer", ""),
        "set": row.get("set", ""),
        "warehouse_code": row.get("warehouse_code", ""),
        "price": row.get("cena") or row.get("price", ""),
        "image": row.get("image1", row.get("images", "")),
        "variant": variant,
        "sold": row.get("sold", ""),
        "added_at": row.get("added_at") or date.today().isoformat(),
    }


def load_csv_data(app):
    """Load a CSV file and merge duplicate rows."""
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return

    with open(file_path, encoding="utf-8") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)

        def norm_header(name: str) -> str:
            normalized = name.strip().lower()
            if normalized == "images 1":
                return "image1"
            return normalized

        fieldnames = [norm_header(fn) for fn in reader.fieldnames or []]
        rows = []
        for raw_row in reader:
            row = {(norm_header(k) if k else k): v for k, v in raw_row.items()}
            if "warehouse_code" not in row and re.match(r"k\d+r\d+p\d+", str(row.get("product_code", "")).lower()):
                row["warehouse_code"] = row["product_code"]
                row["product_code"] = ""
                if "warehouse_code" not in fieldnames:
                    fieldnames.append("warehouse_code")
            rows.append(row)

    combined = {}
    qty_field = None
    qty_variants = {"stock", "ilość", "ilosc", "quantity", "qty"}

    for row in rows:
        img_val = row.get("image1") or row.get("images", "")
        row["image1"] = img_val
        row["images"] = img_val

        key = (
            f"{row.get('nazwa', '').strip()}|{row.get('numer', '').strip()}|{row.get('set', '').strip()}"
        )
        if qty_field is None:
            for variant in qty_variants:
                if variant in row:
                    qty_field = variant
                    break
        qty = 1
        if qty_field:
            try:
                qty = int(row.get(qty_field, 0))
            except ValueError:
                qty = 1

        warehouse = str(row.get("warehouse_code", "")).strip()

        if key in combined:
            combined[key]["qty"] += qty
            if warehouse:
                combined[key]["warehouses"].add(warehouse)
        else:
            new_row = row.copy()
            new_row["qty"] = qty
            new_row["warehouses"] = set()
            if warehouse:
                new_row["warehouses"].add(warehouse)
            combined[key] = new_row

    for row in combined.values():
        if not row.get("product_code"):
            number = row.get("numer") or row.get("number") or ""
            row["product_code"] = build_product_code(
                row.get("set", ""),
                number,
                row.get("variant"),
            )

    if qty_field is None:
        qty_field = "ilość"
        if qty_field not in fieldnames:
            fieldnames.append(qty_field)

    if "image1" in fieldnames:
        fieldnames[fieldnames.index("image1")] = "images 1"

    save_path = filedialog.asksaveasfilename(
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")]
    )
    if not save_path:
        return

    with open(save_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in combined.values():
            row_out = row.copy()
            row_out[qty_field] = row_out.pop("qty")
            row_out["warehouse_code"] = ";".join(sorted(row_out.pop("warehouses", [])))
            row_out["images 1"] = row_out.get("image1", row_out.get("images", ""))
            if qty_field != "stock":
                row_out.pop("stock", None)
            if qty_field != "ilość":
                row_out.pop("ilość", None)
            writer.writerow({k: row_out.get(k, "") for k in fieldnames})

    messagebox.showinfo("Sukces", "Plik CSV został scalony i zapisany.")


def export_csv(app, path: str = COLLECTION_EXPORT_CSV):
    """Export collected data to the collection CSV file."""

    combined = load_collection_export(path)

    for row in app.output_data:
        if row is None:
            continue
        row_copy = row.copy()
        product_code = str(row_copy.get("product_code", ""))
        if not product_code:
            product_code = build_product_code(
                row_copy.get("set", ""),
                row_copy.get("numer", ""),
                row_copy.get("variant"),
            )
            row_copy["product_code"] = product_code
        formatted = format_collection_row(row_copy)
        key = formatted["product_code"] or formatted["warehouse_code"] or formatted["name"]
        combined[key] = formatted

    with open(path, mode="w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=COLLECTION_FIELDNAMES, delimiter=";"
        )
        writer.writeheader()
        for row in combined.values():
            writer.writerow(row)

    append_warehouse_csv(app)
    messagebox.showinfo("Sukces", "Plik kolekcji został zapisany.")
    app.back_to_welcome()


def append_warehouse_csv(app, path: str = WAREHOUSE_CSV):
    """Append all collected rows to the warehouse CSV."""
    fieldnames = WAREHOUSE_FIELDNAMES

    file_exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        if not file_exists:
            writer.writeheader()
        for row in app.output_data:
            if row is None:
                continue
            writer.writerow(format_warehouse_row(row))

    # Recompute and cache inventory statistics to include newly written rows
    get_inventory_stats(path, force=True)

    if hasattr(app, "update_inventory_stats"):
        try:
            app.update_inventory_stats(force=True)
        except TclError:
            pass

