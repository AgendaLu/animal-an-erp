"""
Environment configuration for Animal-AN ERP
Supports: development, testing, production
"""
import os
from pathlib import Path
from typing import Optional


class Config:
    """Base configuration"""

    # Database
    DB_PATH: Optional[Path] = None
    DB_BACKUP_ENABLED = True
    DB_AUTO_MIGRATE = True

    # Logging
    LOG_LEVEL = "INFO"
    LOG_DIR = Path(__file__).parent.parent / "logs"

    # API
    API_HOST = "127.0.0.1"
    API_PORT = 8000
    API_DEBUG = False
    API_RELOAD = False

    # Import
    IMPORT_STRICT_VALIDATION = True
    IMPORT_SKIP_DUPLICATES = True

    # General
    ENVIRONMENT_NAME = "base"

    def __repr__(self):
        return f"<{self.__class__.__name__}>"


class DevelopmentConfig(Config):
    """Development environment configuration"""

    ENVIRONMENT_NAME = "development"
    LOG_LEVEL = "DEBUG"
    API_HOST = "127.0.0.1"
    API_PORT = 8000
    API_DEBUG = True
    API_RELOAD = True
    DB_BACKUP_ENABLED = False  # Skip backup on every init
    IMPORT_STRICT_VALIDATION = False  # Allow flexible validation


class TestingConfig(Config):
    """Testing environment configuration"""

    ENVIRONMENT_NAME = "testing"
    LOG_LEVEL = "INFO"
    API_HOST = "127.0.0.1"
    API_PORT = 8001
    API_DEBUG = False
    API_RELOAD = False
    DB_PATH = Path(":memory:")  # In-memory database
    DB_BACKUP_ENABLED = False
    DB_AUTO_MIGRATE = True
    IMPORT_STRICT_VALIDATION = True


class ProductionConfig(Config):
    """Production environment configuration"""

    ENVIRONMENT_NAME = "production"
    LOG_LEVEL = "INFO"
    API_HOST = "0.0.0.0"  # Listen on all interfaces
    API_PORT = 8000
    API_DEBUG = False
    API_RELOAD = False
    DB_BACKUP_ENABLED = True  # Always backup before migrate
    IMPORT_STRICT_VALIDATION = True


# Environment detection
def _get_environment_name() -> str:
    """Get environment name from environment variable or default to development"""
    env = os.getenv("ANIMAL_AN_ENV", "development").lower()
    if env not in ("development", "testing", "production"):
        env = "development"
    return env


# Current environment
ENVIRONMENT = _get_environment_name()

# Configuration mapping
_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env: Optional[str] = None) -> Config:
    """Get configuration for specified environment

    Args:
        env: Environment name (development, testing, production).
             If None, uses current ENVIRONMENT.

    Returns:
        Configuration instance for the environment
    """
    if env is None:
        env = ENVIRONMENT

    env = env.lower()
    if env not in _CONFIGS:
        raise ValueError(f"Unknown environment: {env}")

    config_class = _CONFIGS[env]
    config = config_class()

    # Set default database path if not specified
    if config.DB_PATH is None:
        data_dir = Path(__file__).parent.parent / "data"
        config.DB_PATH = data_dir / "animal_an.db"

    return config


# Export current config
current_config = get_config()


def print_config():
    """Print current configuration (for debugging)"""
    print("\n" + "=" * 70)
    print(f"ENVIRONMENT CONFIGURATION: {ENVIRONMENT.upper()}")
    print("=" * 70)
    config = current_config
    for key, value in sorted(config.__dict__.items()):
        if not key.startswith("_"):
            print(f"{key:<30} {value}")
    print("=" * 70)


if __name__ == "__main__":
    print_config()
