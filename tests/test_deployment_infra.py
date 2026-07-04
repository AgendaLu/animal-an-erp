"""部署基礎設施測試 — 環境設定、schema migration、CSV 匯入、備份 CLI。

備份核心(建立/還原/清理)已在 test_database_init.py 覆蓋;
這裡補 CLI 錯誤路徑與各解析器/migration 的行為。
"""
import csv
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.environments import get_config, _get_environment_name  # noqa: E402
from models.database import DatabaseManager  # noqa: E402
from scripts.migrate_v03 import migrate  # noqa: E402
from scripts.import_data import CSVImporter  # noqa: E402
from utils import backup as backup_cli  # noqa: E402
from utils.backup import DatabaseBackup, format_size  # noqa: E402


# ------------------------------------------------------------------ config

class TestEnvironmentConfig:
    def test_testing_profile(self):
        cfg = get_config("testing")
        assert cfg.ENVIRONMENT_NAME == "testing"
        assert cfg.API_PORT == 8001
        assert cfg.DB_PATH == Path(":memory:")
        assert cfg.DB_BACKUP_ENABLED is False

    def test_production_profile(self):
        cfg = get_config("production")
        assert cfg.API_HOST == "0.0.0.0"
        assert cfg.DB_BACKUP_ENABLED is True
        assert cfg.API_RELOAD is False
        assert cfg.DB_PATH.name == "animal_an.db"  # 預設路徑自動補齊

    def test_development_profile(self):
        cfg = get_config("development")
        assert cfg.API_RELOAD is True
        assert cfg.API_HOST == "127.0.0.1"
        assert cfg.DB_PATH.name == "animal_an.db"

    def test_unknown_environment_raises(self):
        with pytest.raises(ValueError, match="Unknown environment"):
            get_config("staging")

    def test_env_var_detection(self, monkeypatch):
        monkeypatch.setenv("ANIMAL_AN_ENV", "PRODUCTION")
        assert _get_environment_name() == "production"
        monkeypatch.setenv("ANIMAL_AN_ENV", "not-an-env")
        assert _get_environment_name() == "development"  # 非法值 fallback
        monkeypatch.delenv("ANIMAL_AN_ENV")
        assert _get_environment_name() == "development"


# ------------------------------------------------------------------ migration

LEGACY_DDL = [
    "CREATE TABLE materials (id INTEGER PRIMARY KEY, code VARCHAR(50), "
    "name VARCHAR(100), unit VARCHAR(20))",
    "CREATE TABLE customers (id INTEGER PRIMARY KEY, code VARCHAR(20), "
    "name VARCHAR(100), customer_type VARCHAR(50))",
    "CREATE TABLE suppliers (id INTEGER PRIMARY KEY, code VARCHAR(20), "
    "name VARCHAR(100))",
    "CREATE TABLE products (id INTEGER PRIMARY KEY, code VARCHAR(50), "
    "name VARCHAR(100))",
    "CREATE TABLE material_batches (id INTEGER PRIMARY KEY)",
    "CREATE TABLE inventory_transactions (id INTEGER PRIMARY KEY)",
    # 刻意不建 batches 表,驗證缺表跳過
]


def make_legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    for ddl in LEGACY_DDL:
        conn.execute(ddl)
    conn.executemany(
        "INSERT INTO customers (code, name, customer_type) VALUES (?,?,?)",
        [("C1", "客戶1", "Veterinary"), ("C2", "客戶2", "Farm"),
         ("C3", "客戶3", "WeirdType"), ("C4", "客戶4", "PIG_FARM")])
    conn.commit()
    conn.close()


def columns(path: Path, table: str) -> set:
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


class TestMigrateV03:
    def test_adds_columns_and_maps_customer_types(self, tmp_path):
        db = tmp_path / "legacy.db"
        make_legacy_db(db)

        migrate(db)

        assert "product_type" in columns(db, "materials")
        assert "current_balance" in columns(db, "customers")
        assert "short_name" in columns(db, "suppliers")
        assert "selling_price" in columns(db, "products")
        assert "unit_cost" in columns(db, "material_batches")
        assert "balance_after" in columns(db, "inventory_transactions")

        conn = sqlite3.connect(db)
        rows = dict(conn.execute("SELECT code, customer_type FROM customers"))
        conn.close()
        assert rows == {"C1": "VET_CLINIC", "C2": "PIG_FARM",
                        "C3": None, "C4": "PIG_FARM"}

    def test_creates_backup_before_migrating(self, tmp_path):
        db = tmp_path / "legacy.db"
        make_legacy_db(db)
        migrate(db)
        backups = list(tmp_path.glob("legacy_pre_v03_*.db"))
        assert len(backups) == 1
        # 備份保留舊 schema(migration 前拷貝)
        assert "product_type" not in columns(backups[0], "materials")

    def test_rerun_is_idempotent(self, tmp_path):
        db = tmp_path / "legacy.db"
        make_legacy_db(db)
        migrate(db)
        cols_first = {t: columns(db, t) for t in ("materials", "customers")}
        migrate(db)  # 缺表(batches)與已存在欄位都應安全跳過
        cols_second = {t: columns(db, t) for t in ("materials", "customers")}
        assert cols_first == cols_second


class TestMigrationDetection:
    def test_fresh_db_needs_no_migration(self, tmp_path):
        dm = DatabaseManager()
        dm.init_db(str(tmp_path / "fresh.db"))
        assert dm._check_db_needs_migration() is False

    def test_legacy_db_flagged_for_migration(self, tmp_path):
        from sqlalchemy import create_engine
        db = tmp_path / "legacy.db"
        make_legacy_db(db)  # 無 sales_invoices 表
        dm = DatabaseManager()
        dm.engine = create_engine(f"sqlite:///{db}")
        assert dm._check_db_needs_migration() is True
        # 還原 singleton,避免影響其他測試
        dm.init_db(str(tmp_path / "fresh.db"))


# ------------------------------------------------------------------ CSV 匯入

@pytest.fixture()
def importer(tmp_path):
    """暫存 DB + 暫存 CSV 目錄的 importer。"""
    dm = DatabaseManager()
    dm.init_db(str(tmp_path / "import.db"))
    yield CSVImporter(tmp_path)


def write_csv(directory: Path, name: str, rows: list) -> None:
    with open(directory / name, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class TestCSVImport:
    def test_import_customers_products_materials(self, importer, tmp_path):
        write_csv(tmp_path, "customers.csv", [dict(
            code="CUST-001", name="永春牧場", customer_type="PIG_FARM")])
        write_csv(tmp_path, "products.csv", [dict(
            code="PROD-001", name="維A 100ml", product_type="SUPPLEMENT",
            selling_price="500")])
        write_csv(tmp_path, "materials.csv", [dict(
            code="BULK-001", name="維A原裝桶", unit="桶", quantity="0",
            min_quantity="2")])

        assert importer.import_customers() == 1
        assert importer.import_products() == 1
        assert importer.import_materials() == 1
        assert importer.import_stats["errors"] == []

    def test_reimport_skips_duplicates(self, importer, tmp_path):
        write_csv(tmp_path, "customers.csv", [dict(
            code="CUST-001", name="永春牧場", customer_type="PIG_FARM")])
        assert importer.import_customers() == 1
        assert importer.import_customers() == 0  # 冪等:重跑跳過

        from models.partner import Customer
        assert importer.session.query(Customer).count() == 1

    def test_bad_enum_recorded_without_aborting(self, importer, tmp_path):
        write_csv(tmp_path, "suppliers.csv", [
            dict(code="SUP-BAD", name="壞類型", supplier_type="NOPE"),
            dict(code="SUP-OK", name="好供應商", supplier_type="MANUFACTURER"),
        ])
        count = importer.import_suppliers()
        assert count == 1  # 壞列跳過,好列照常匯入
        assert len(importer.import_stats["errors"]) == 1
        assert "SUP-BAD" in importer.import_stats["errors"][0]

    def test_run_import_handles_missing_files(self, importer):
        stats = importer.run_import()  # 目錄裡沒有任何 CSV
        assert stats["errors"] == []
        assert stats["suppliers"] == stats["customers"] == 0

    def test_parse_csv_empty_file(self, importer, tmp_path):
        empty = tmp_path / "empty.csv"
        empty.touch()
        assert importer.parse_csv(empty) == []

    def test_date_parser_formats(self, importer):
        parse = importer._parse_date
        assert parse("2026-07-04").date().isoformat() == "2026-07-04"
        assert parse("2026/07/04").date().isoformat() == "2026-07-04"
        assert parse("04/07/2026").date().isoformat() == "2026-07-04"
        assert parse("20260704").date().isoformat() == "2026-07-04"
        assert parse("") is None
        assert parse("not-a-date") is None

    def test_float_parser(self, importer):
        parse = importer._parse_float
        assert parse("1.5") == 1.5
        assert parse("1,5") == 1.5  # 逗號視為小數點
        assert parse("") == 0.0
        # 已知缺口:千分位格式解析失敗會靜默歸零(見 docs/testing_strategy.md)
        assert parse("1,234.56") == 0.0

    def test_bool_parser(self, importer):
        parse = importer._parse_bool
        assert parse("TRUE") is True
        assert parse("yes") is True
        assert parse("1") is True
        assert parse("no") is False
        assert parse("") is False


# ------------------------------------------------------------------ 備份 CLI

class TestBackupCLI:
    def test_no_args_prints_usage(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["backup"])
        assert backup_cli.main() == 1
        assert "Usage" in capsys.readouterr().out

    def test_restore_requires_file_argument(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["backup", "restore"])
        assert backup_cli.main() == 1
        assert "requires backup file" in capsys.readouterr().out

    def test_unknown_command(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["backup", "frobnicate"])
        assert backup_cli.main() == 1
        assert "Unknown command" in capsys.readouterr().out

    def test_format_size(self):
        assert format_size(512) == "512.0 KB"
        assert format_size(2048) == "2.0 MB"

    def test_cmd_create_list_cleanup_roundtrip(self, tmp_path, capsys):
        db = tmp_path / "test.db"
        db.write_bytes(b"data")
        assert backup_cli.cmd_create(str(db)) == 0
        assert "✓" in capsys.readouterr().out
        assert backup_cli.cmd_list(str(db)) == 0
        assert "test_backup_" in capsys.readouterr().out
        assert backup_cli.cmd_cleanup(str(db), days=30) == 0
        assert len(DatabaseBackup(db).list_backups()) == 1  # 新備份不清

    def test_cmd_restore_roundtrip(self, tmp_path, capsys):
        db = tmp_path / "test.db"
        db.write_bytes(b"original")
        backup_path = DatabaseBackup(db).create_backup()
        db.write_bytes(b"corrupted")
        assert backup_cli.cmd_restore(str(db), str(backup_path)) == 0
        assert db.read_bytes() == b"original"
        assert backup_cli.cmd_restore(str(db), str(tmp_path / "ghost.db")) == 1

    def test_cmd_create_missing_db_fails(self, tmp_path, capsys):
        assert backup_cli.cmd_create(str(tmp_path / "ghost.db")) == 1
        assert "✗" in capsys.readouterr().out

    def test_create_backup_missing_source_returns_none(self, tmp_path):
        mgr = DatabaseBackup(tmp_path / "ghost.db")
        assert mgr.create_backup() is None

    def test_restore_missing_backup_returns_false(self, tmp_path):
        db = tmp_path / "test.db"
        db.write_bytes(b"data")
        mgr = DatabaseBackup(db)
        assert mgr.restore_backup(tmp_path / "no-such-backup.db") is False
