"""One-shot migration for spec v0.3 (分裝進銷存).

Adds new columns to existing tables in data/animal_an.db (and data/inventory.db
if present). All additions are nullable / defaulted, so legacy rows keep loading.
Creates a timestamped backup of each db file before touching it.

Usage:
    python scripts/migrate_v03.py                 # migrate data/animal_an.db + data/inventory.db
    python scripts/migrate_v03.py PATH [PATH...]  # migrate the given database file(s)
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_CANDIDATES = [ROOT / "data" / "animal_an.db", ROOT / "data" / "inventory.db"]

# table -> [(column, DDL type/default)]
NEW_COLUMNS = {
    "materials": [
        ("product_type", "VARCHAR(14)"),
        ("storage_type", "VARCHAR(12)"),
        ("min_temperature", "FLOAT"),
        ("max_temperature", "FLOAT"),
        ("shelf_life_months", "INTEGER"),
        ("default_supplier_id", "INTEGER REFERENCES suppliers(id)"),
        ("registration_number", "VARCHAR(50)"),
        ("country_of_origin", "VARCHAR(50)"),
    ],
    "material_batches": [
        ("lot_number", "VARCHAR(50)"),
        ("unit_cost", "FLOAT"),
        ("supplier_id", "INTEGER REFERENCES suppliers(id)"),
        ("quality_status", "VARCHAR(11)"),
    ],
    "inventory_transactions": [
        ("item_kind", "VARCHAR(8) DEFAULT 'BULK'"),
        ("unit_cost", "FLOAT"),
        ("balance_after", "FLOAT"),
    ],
    "products": [
        ("bulk_item_id", "INTEGER REFERENCES materials(id)"),
        ("units_per_bulk", "FLOAT"),
        ("selling_price", "FLOAT"),
        ("spec", "VARCHAR(200)"),
        ("package_size", "FLOAT"),
        ("package_unit", "VARCHAR(20)"),
        ("units_per_package", "FLOAT"),
        ("dosage_form", "VARCHAR(50)"),
        ("concentration", "VARCHAR(50)"),
        ("active_ingredient", "VARCHAR(200)"),
        ("barcode", "VARCHAR(50)"),
    ],
    "batches": [
        ("parent_bulk_batch_id", "INTEGER REFERENCES material_batches(id)"),
    ],
    "suppliers": [
        ("short_name", "VARCHAR(50)"),
        ("supplier_type", "VARCHAR(12)"),
        ("country", "VARCHAR(50)"),
        ("contact_title", "VARCHAR(50)"),
        ("fax", "VARCHAR(20)"),
        ("mobile", "VARCHAR(20)"),
        ("payment_method", "VARCHAR(50)"),
        ("currency", "VARCHAR(10)"),
        ("bank_name", "VARCHAR(100)"),
        ("bank_branch", "VARCHAR(100)"),
        ("bank_swift", "VARCHAR(20)"),
        ("license_number", "VARCHAR(50)"),
        ("license_expiry", "DATE"),
        ("rating", "VARCHAR(5)"),
        ("notes", "TEXT"),
    ],
    "customers": [
        ("short_name", "VARCHAR(50)"),
        ("contact_title", "VARCHAR(50)"),
        ("fax", "VARCHAR(20)"),
        ("mobile", "VARCHAR(20)"),
        ("billing_address", "TEXT"),
        ("shipping_address", "TEXT"),
        ("invoice_title", "VARCHAR(100)"),
        ("current_balance", "FLOAT DEFAULT 0"),
        ("sales_rep", "VARCHAR(50)"),
        ("farm_license", "VARCHAR(50)"),
        ("notes", "TEXT"),
    ],
}

# customers.customer_type was free text; convert known legacy values to the
# new enum names, anything unknown becomes NULL so rows still load.
CUSTOMER_TYPE_MAP = {
    "Veterinary": "VET_CLINIC",
    "Farm": "PIG_FARM",
    "Retail": "RETAIL",
}


def existing_columns(conn: sqlite3.Connection, table: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def migrate(db_path: Path) -> None:
    backup = db_path.with_name(
        f"{db_path.stem}_pre_v03_{datetime.now():%Y%m%d_%H%M%S}{db_path.suffix}"
    )
    shutil.copy2(db_path, backup)
    print(f"[backup] {backup}")

    conn = sqlite3.connect(db_path)
    try:
        added = 0
        for table, cols in NEW_COLUMNS.items():
            if not table_exists(conn, table):
                print(f"[skip] table {table} not in {db_path.name}")
                continue
            have = existing_columns(conn, table)
            for name, ddl in cols:
                if name in have:
                    continue
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                added += 1
                print(f"[add ] {table}.{name}")

        if table_exists(conn, "customers"):
            for old, new in CUSTOMER_TYPE_MAP.items():
                conn.execute(
                    "UPDATE customers SET customer_type=? WHERE customer_type=?",
                    (new, old),
                )
            conn.execute(
                "UPDATE customers SET customer_type=NULL WHERE customer_type IS NOT NULL "
                "AND customer_type NOT IN ('PIG_FARM','VET_CLINIC','FEED_MILL','DISTRIBUTOR','RETAIL')"
            )

        conn.commit()
        print(f"[done] {db_path.name}: {added} columns added")
    finally:
        conn.close()


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if args:
        targets = [Path(a) for a in args]
        missing = [p for p in targets if not p.exists()]
        if missing:
            for p in missing:
                print(f"[error] database not found: {p}")
            return 1
    else:
        targets = [p for p in DB_CANDIDATES if p.exists()]
        if not targets:
            print("No database file found; new tables will be created on next app start.")
            return 0
    for db in targets:
        migrate(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
