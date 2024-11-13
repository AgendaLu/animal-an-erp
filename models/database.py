from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path
import logging
from typing import Optional
from contextlib import contextmanager

from .base import Base

# Set up logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database management class"""
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
            self.initialized = True
    
    def init_db(self, db_path: Optional[str] = None) -> None:
        """Initialize the database"""
        try:
            if db_path is None:
                # Create data directory if it doesn't exist
                data_dir = Path(__file__).parent.parent / 'data'
                data_dir.mkdir(exist_ok=True)
                db_path = data_dir / 'animal_an.db'
            
            # Create engine
            self.engine = create_engine(
                f"sqlite:///{db_path}",
                echo=False,
                connect_args={"check_same_thread": False}
            )
            
            # Create all tables
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