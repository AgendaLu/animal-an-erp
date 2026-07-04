"""
Tests for database initialization, backup, and restoration
"""
import pytest
import tempfile
from pathlib import Path
import shutil

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import DatabaseManager
from utils.backup import DatabaseBackup


class TestDatabaseInitialization:
    """Test database initialization"""

    def test_init_creates_database(self):
        """Test that init_db creates database file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            assert db_path.exists()
            assert db_path.stat().st_size > 0

    def test_init_creates_tables(self):
        """Test that init_db creates all required tables"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            # Check if tables are created
            from sqlalchemy import inspect
            inspector = inspect(db_manager.engine)
            tables = inspector.get_table_names()

            # Check for key tables
            required_tables = [
                'materials', 'batches', 'products',
                'suppliers', 'customers',
                'sales_invoices', 'purchase_invoices'
            ]

            for table in required_tables:
                assert table in tables, f"Table {table} not found"

    def test_get_session_works(self):
        """Test that get_session returns valid session"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            session = db_manager.get_session()
            assert session is not None

            # Test query
            from models.partner import Supplier
            count = session.query(Supplier).count()
            assert count >= 0

            session.close()

    def test_session_scope_context_manager(self):
        """Test session_scope context manager"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            # Test context manager
            with db_manager.session_scope() as session:
                from models.partner import Supplier
                count = session.query(Supplier).count()
                assert count >= 0


class TestAutoMigrationOnInit:
    """Auto-migration during init_db must act on the db_path passed in,
    never on the real data/ directory (regression: _run_migrations used to
    invoke migrate_v03.py without arguments, which only migrates data/*.db)
    """

    LEGACY_DDL = [
        # pre-v0.3 schema: no sales_invoices table, no v0.3 columns
        "CREATE TABLE materials (id INTEGER PRIMARY KEY, code VARCHAR(50), "
        "name VARCHAR(100), unit VARCHAR(20))",
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, code VARCHAR(20), "
        "name VARCHAR(100), customer_type VARCHAR(50))",
    ]

    def make_legacy_db(self, path):
        import sqlite3
        conn = sqlite3.connect(path)
        for ddl in self.LEGACY_DDL:
            conn.execute(ddl)
        conn.execute(
            "INSERT INTO customers (code, name, customer_type) "
            "VALUES ('C1', 'Legacy Customer', 'Veterinary')"
        )
        conn.commit()
        conn.close()

    def columns(self, db_path, table):
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        finally:
            conn.close()

    def test_init_migrates_the_given_legacy_db(self):
        """init_db on a legacy DB migrates that file in place"""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.db"
            self.make_legacy_db(db_path)
            assert "product_type" not in self.columns(db_path, "materials")

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            # v0.3 columns added to the file we passed in
            assert "product_type" in self.columns(db_path, "materials")
            assert "current_balance" in self.columns(db_path, "customers")

            # legacy customer_type value mapped to the new enum name
            conn = sqlite3.connect(db_path)
            (customer_type,) = conn.execute(
                "SELECT customer_type FROM customers WHERE code='C1'"
            ).fetchone()
            conn.close()
            assert customer_type == "VET_CLINIC"

            # migration backup created next to the target db, not in data/
            assert list(Path(tmpdir).glob("legacy_pre_v03_*.db"))

            # missing v0.3 tables created afterwards by create_all
            from sqlalchemy import inspect
            assert "sales_invoices" in inspect(db_manager.engine).get_table_names()

    def test_init_on_legacy_db_leaves_data_dir_untouched(self):
        """Migrating a legacy DB elsewhere must not modify or back up data/*"""
        data_dir = Path(__file__).resolve().parent.parent / "data"

        def snapshot():
            if not data_dir.exists():
                return {}
            return {p.name: p.stat().st_mtime_ns for p in data_dir.iterdir()}

        before = snapshot()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.db"
            self.make_legacy_db(db_path)
            DatabaseManager().init_db(str(db_path))
        assert snapshot() == before


class TestDatabaseBackup:
    """Test backup and restore functionality"""

    def test_create_backup(self):
        """Test backup creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create database
            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            # Create backup
            backup_mgr = DatabaseBackup(str(db_path))
            backup_path = backup_mgr.create_backup()

            assert backup_path is not None
            assert backup_path.exists()
            assert "backup" in backup_path.name

    def test_list_backups(self):
        """Test listing backups"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create database
            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            # Create multiple backups
            backup_mgr = DatabaseBackup(str(db_path))
            backup1 = backup_mgr.create_backup()

            # List backups
            backups = backup_mgr.list_backups()
            assert len(backups) > 0
            assert any(backup1.name in b['filename'] for b in backups)

    def test_restore_backup(self):
        """Test backup restoration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create database with test data
            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            # Add test data
            with db_manager.session_scope() as session:
                from models.partner import Supplier
                supplier = Supplier(
                    code="TEST-001",
                    name="Test Supplier",
                    supplier_type="MANUFACTURER",
                    contact_person="Test Contact",
                    phone="000-0000",
                    address="Test Address",
                    credit_term_days=30,
                )
                session.add(supplier)

            # Get data before backup
            with db_manager.session_scope() as session:
                from models.partner import Supplier
                count_before = session.query(Supplier).count()

            # Create backup
            backup_mgr = DatabaseBackup(str(db_path))
            backup_path = backup_mgr.create_backup()

            # Modify database
            with db_manager.session_scope() as session:
                from models.partner import Supplier
                # Delete all suppliers
                session.query(Supplier).delete()

            # Verify deletion
            with db_manager.session_scope() as session:
                from models.partner import Supplier
                count_after_delete = session.query(Supplier).count()
            assert count_after_delete == 0

            # Restore backup
            success = backup_mgr.restore_backup(str(backup_path))
            assert success

            # Reinitialize db_manager to reload database
            db_manager2 = DatabaseManager()
            db_manager2.init_db(str(db_path))

            # Verify restoration
            with db_manager2.session_scope() as session:
                from models.partner import Supplier
                count_after_restore = session.query(Supplier).count()
            assert count_after_restore == count_before

    def test_cleanup_keeps_recent_backups(self):
        """Recent backups should survive cleanup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            backup_mgr = DatabaseBackup(str(db_path))
            backup_mgr.create_backup()

            # A freshly created backup is well within the retention window
            deleted = backup_mgr.cleanup_old_backups(days=30)
            assert deleted == 0
            assert len(backup_mgr.list_backups()) == 1

    def test_cleanup_removes_aged_backups(self):
        """Backups older than the retention window should be deleted"""
        import os
        from datetime import datetime, timedelta

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            backup_mgr = DatabaseBackup(str(db_path))
            backup_path = backup_mgr.create_backup()

            # Age the backup file well past the retention window
            old_time = (datetime.now() - timedelta(days=60)).timestamp()
            os.utime(backup_path, (old_time, old_time))

            backups_before = backup_mgr.list_backups()
            assert len(backups_before) == 1

            deleted = backup_mgr.cleanup_old_backups(days=30)
            assert deleted == 1
            assert len(backup_mgr.list_backups()) == 0

    def test_cleanup_rejects_invalid_days(self):
        """Non-positive retention should be treated as invalid, deleting nothing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db_manager = DatabaseManager()
            db_manager.init_db(str(db_path))

            backup_mgr = DatabaseBackup(str(db_path))
            backup_mgr.create_backup()

            assert backup_mgr.cleanup_old_backups(days=0) == 0
            assert len(backup_mgr.list_backups()) == 1


class TestCSVImport:
    """Test CSV import functionality"""

    def test_import_suppliers(self):
        """Test supplier CSV import"""
        import csv
        import tempfile
        from scripts.import_data import CSVImporter

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test CSV
            csv_path = Path(tmpdir) / "suppliers.csv"
            with open(csv_path, 'w', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'code', 'name', 'supplier_type', 'country'
                ])
                writer.writeheader()
                writer.writerow({
                    'code': 'TEST-SUP-001',
                    'name': 'Test Supplier',
                    'supplier_type': 'MANUFACTURER',
                    'country': 'Japan'
                })

            # Initialize database
            db_path = Path(tmpdir) / "test.db"
            from models.database import DatabaseManager
            db_mgr = DatabaseManager()
            db_mgr.init_db(str(db_path))

            # Import
            importer = CSVImporter(Path(tmpdir))
            count = importer.import_suppliers('suppliers.csv')

            assert count == 1

            # Verify import
            from models.partner import Supplier
            supplier = db_mgr.get_session().query(Supplier).filter_by(
                code='TEST-SUP-001'
            ).first()
            assert supplier is not None
            assert supplier.name == 'Test Supplier'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
