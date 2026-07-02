"""
Database backup and restore utilities
Supports: create, restore, list, cleanup operations
"""
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Union
import logging

from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseBackup:
    """Manage database backups and restoration"""

    # Backup file naming convention: {db_name}_backup_{timestamp}.db
    BACKUP_SUFFIX = "_backup_"

    def __init__(self, db_path: Union[str, Path]):
        """Initialize backup manager with database path"""
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.parent
        self.db_name = self.db_path.stem  # filename without .db

    def create_backup(self) -> Optional[Path]:
        """
        Create a timestamped backup of the database

        Returns:
            Path to the created backup file, or None if failed
        """
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
            return None

        # Microsecond precision so backups taken within the same second
        # (e.g. a safety backup during restore) never collide and overwrite.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_filename = f"{self.db_name}{self.BACKUP_SUFFIX}{timestamp}.db"
        backup_path = self.backup_dir / backup_filename

        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            return None

    def restore_backup(self, backup_file: Union[str, Path]) -> bool:
        """
        Restore database from a backup file

        Args:
            backup_file: Path to the backup file

        Returns:
            True if restore successful, False otherwise
        """
        backup_path = Path(backup_file)

        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        try:
            # Create a safety backup of current database before restoring.
            # Guard against overwriting the very backup we're restoring from.
            if self.db_path.exists():
                safety_backup = self.create_backup()
                if safety_backup and safety_backup.resolve() == backup_path.resolve():
                    logger.error(
                        "Safety backup collided with restore source; aborting to "
                        "avoid corrupting the backup"
                    )
                    return False
                if safety_backup:
                    logger.info(f"Safety backup created: {safety_backup}")

            # Restore from backup
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Database restored from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore backup: {str(e)}")
            return False

    def list_backups(self) -> List[dict]:
        """
        List all backups for this database

        Returns:
            List of dicts with backup info: {filename, path, size, timestamp}
        """
        backups = []

        if not self.backup_dir.exists():
            return backups

        # Find all backup files matching pattern: {db_name}_backup_*.db
        pattern = f"{self.db_name}{self.BACKUP_SUFFIX}*.db"

        for backup_file in sorted(self.backup_dir.glob(pattern), reverse=True):
            stat = backup_file.stat()
            size_kb = stat.st_size / 1024

            # Extract timestamp from filename
            filename = backup_file.name
            timestamp_str = filename.split(self.BACKUP_SUFFIX)[-1].replace('.db', '')

            backups.append({
                'filename': filename,
                'path': str(backup_file),
                'size_kb': size_kb,
                'timestamp': timestamp_str,
                'mtime': datetime.fromtimestamp(stat.st_mtime)
            })

        return backups

    def cleanup_old_backups(self, days: int = 30) -> int:
        """
        Delete backups older than specified days

        Args:
            days: Keep backups from the last N days (default: 30)

        Returns:
            Number of backups deleted
        """
        if days <= 0:
            logger.warning("Days must be positive")
            return 0

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        backups = self.list_backups()
        for backup in backups:
            if backup['mtime'] < cutoff_date:
                try:
                    Path(backup['path']).unlink()
                    logger.info(f"Deleted old backup: {backup['filename']}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup['filename']}: {str(e)}")

        logger.info(f"Cleanup complete: {deleted_count} backups deleted")
        return deleted_count


def format_size(size_kb: float) -> str:
    """Format file size for display"""
    if size_kb < 1024:
        return f"{size_kb:.1f} KB"
    else:
        return f"{size_kb / 1024:.1f} MB"


def cmd_create(db_path: str):
    """Command: create backup"""
    backup_mgr = DatabaseBackup(db_path)
    result = backup_mgr.create_backup()
    if result:
        print(f"✓ Backup created: {result.name}")
        return 0
    else:
        print("✗ Failed to create backup")
        return 1


def cmd_restore(db_path: str, backup_file: str) -> int:
    """Command: restore from backup"""
    backup_mgr = DatabaseBackup(db_path)
    if backup_mgr.restore_backup(backup_file):
        print(f"✓ Database restored from: {backup_file}")
        return 0
    else:
        print("✗ Failed to restore database")
        return 1


def cmd_list(db_path: str) -> int:
    """Command: list backups"""
    backup_mgr = DatabaseBackup(db_path)
    backups = backup_mgr.list_backups()

    if not backups:
        print("No backups found")
        return 0

    print(f"Database backups for: {backup_mgr.db_path}")
    print("=" * 70)
    print(f"{'Backup File':<40} {'Size':>10} {'Created':<20}")
    print("-" * 70)

    for backup in backups:
        size_str = format_size(backup['size_kb'])
        mtime_str = backup['mtime'].strftime("%Y-%m-%d %H:%M:%S")
        print(f"{backup['filename']:<40} {size_str:>10} {mtime_str:<20}")

    print("=" * 70)
    return 0


def cmd_cleanup(db_path: str, days: int) -> int:
    """Command: cleanup old backups"""
    backup_mgr = DatabaseBackup(db_path)
    deleted = backup_mgr.cleanup_old_backups(days)
    print(f"✓ Cleanup complete: {deleted} backups deleted (kept last {days} days)")
    return 0


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python -m utils.backup <command> [options]")
        print("\nCommands:")
        print("  create                    Create a backup")
        print("  restore <backup_file>     Restore from backup")
        print("  list                      List all backups")
        print("  clean --days <N>          Delete backups older than N days (default: 30)")
        print("\nExample:")
        print("  python -m utils.backup create")
        print("  python -m utils.backup list")
        print("  python -m utils.backup restore animal_an_backup_20260701_120000.db")
        print("  python -m utils.backup clean --days 30")
        return 1

    # Locate database
    db_path = Path(__file__).parent.parent / "data" / "animal_an.db"

    command = sys.argv[1].lower()

    if command == "create":
        return cmd_create(str(db_path))

    elif command == "restore":
        if len(sys.argv) < 3:
            print("Error: restore requires backup file argument")
            print("Usage: python -m utils.backup restore <backup_file>")
            return 1
        backup_file = sys.argv[2]
        return cmd_restore(str(db_path), backup_file)

    elif command == "list":
        return cmd_list(str(db_path))

    elif command == "clean":
        days = 30
        if len(sys.argv) >= 4 and sys.argv[2] == "--days":
            try:
                days = int(sys.argv[3])
            except ValueError:
                print("Error: days must be an integer")
                return 1
        return cmd_cleanup(str(db_path), days)

    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
