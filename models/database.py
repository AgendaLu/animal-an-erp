from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path
import logging
from typing import Optional
from contextlib import contextmanager

from .base import Base

# Set up logging
logger = logging.getLogger(__name__)

DB_VERSION_CURRENT = "0.3"  # Current database schema version
DB_VERSION_FIELD = "_db_version"  # Metadata field for version tracking

class DatabaseManager:
    """Database management class with versioning and migration support"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if not self.initialized:
            self.engine = None
            self.SessionLocal = None
            self.db_path = None
            self.initialized = True

    def _check_db_needs_migration(self) -> bool:
        """Check if database needs migration (version < 0.3)"""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()

            # Check if we have sales_invoices table (v0.3 feature)
            return 'sales_invoices' not in tables
        except Exception as e:
            logger.warning(f"Could not check database version: {e}")
            return False

    def _run_migrations(self) -> bool:
        """Run any pending database migrations on self.db_path"""
        try:
            from scripts.migrate_v03 import migrate

            logger.info(f"Running v0.3 migration on {self.db_path}")
            migrate(self.db_path)
            logger.info("Migration completed successfully")
            return True
        except Exception as e:
            logger.error(f"Migration error: {e}")
            return False

    def _backup_before_init(self) -> bool:
        """Create a backup before database initialization"""
        try:
            from utils.backup import DatabaseBackup
            if self.db_path and Path(self.db_path).exists():
                backup_mgr = DatabaseBackup(self.db_path)
                backup_path = backup_mgr.create_backup()
                if backup_path:
                    logger.info(f"Backup created before initialization: {backup_path}")
                    return True
            return True
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")
            return True  # Don't fail if backup fails

    def init_db(self, db_path: Optional[str] = None) -> None:
        """Initialize the database with versioning and migration support"""
        try:
            if db_path is None:
                # Create data directory if it doesn't exist
                data_dir = Path(__file__).parent.parent / 'data'
                data_dir.mkdir(exist_ok=True)
                db_path = data_dir / 'animal_an.db'

            self.db_path = Path(db_path)
            is_new_db = not self.db_path.exists()

            # Create engine
            self.engine = create_engine(
                f"sqlite:///{db_path}",
                echo=False,
                connect_args={"check_same_thread": False}
            )

            # Check if migration is needed before creating tables
            if not is_new_db and self._check_db_needs_migration():
                logger.info("Database migration needed (version < 0.3)")
                self._backup_before_init()
                if not self._run_migrations():
                    logger.error("Migration failed")
                    raise RuntimeError("Database migration failed")

            # Create all tables (safe for existing DBs, as create_all only creates missing tables)
            Base.metadata.create_all(self.engine)

            # Create sessionmaker
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session"""
        if self.SessionLocal is None:
            self.init_db()
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

# Create global instance
db_manager = DatabaseManager()

# For backwards compatibility
def init_db() -> Session:
    """Initialize the database and return a session (legacy support)"""
    db_manager.init_db()
    return db_manager.get_session()

# Function to get database session
def get_db() -> Session:
    """Get database session"""
    return db_manager.get_session()