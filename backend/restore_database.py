"""Restore a verified SQLite backup without modifying the target on failure."""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


def _readonly_database_uri(path: Path) -> str:
    """Build a correctly escaped SQLite file URI for read-only access."""
    return path.resolve().as_uri() + "?mode=ro"


def _integrity(path: Path) -> tuple[bool, str]:
    try:
        with sqlite3.connect(_readonly_database_uri(path), uri=True) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        if not result or result[0] != "ok":
            return False, str(result[0] if result else "no_integrity_result")
        if "market_bars" not in tables:
            return False, "market_bars_table_missing"
        return True, "ok"
    except sqlite3.Error as exc:
        return False, type(exc).__name__


def restore_backup(backup: Path, destination: Path, overwrite: bool = False) -> dict:
    backup = backup.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if backup == destination:
        raise ValueError("backup_and_destination_must_differ")
    if not backup.is_file():
        raise FileNotFoundError("backup_file_not_found")
    if destination.exists() and not overwrite:
        raise FileExistsError("destination_exists_use_overwrite")
    backup_ok, backup_status = _integrity(backup)
    if not backup_ok:
        raise ValueError("backup_integrity_failed:" + backup_status)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=destination.name + ".", suffix=".restore.tmp",
            dir=destination.parent, delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with sqlite3.connect(_readonly_database_uri(backup), uri=True) as source_db:
            with sqlite3.connect(temporary_path) as target_db:
                source_db.backup(target_db)
        restored_ok, restored_status = _integrity(temporary_path)
        if not restored_ok:
            raise ValueError("restored_database_integrity_failed:" + restored_status)
        if destination.exists() and not overwrite:
            raise FileExistsError("destination_exists_use_overwrite")
        os.replace(temporary_path, destination)
        temporary_path = None
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return {
            "status": "restored_and_verified",
            "sha256": digest,
            "backup": backup.name,
            "destination": str(destination),
            "bytes": destination.stat().st_size,
            "backup_integrity": backup_status,
            "restored_integrity": restored_status,
        }
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Restore and verify a MARKET-MIND SQLite backup."
    )
    parser.add_argument("backup", help="Verified backup file path")
    parser.add_argument("destination", help="Target database path")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Replace an existing target only after the restored copy passes integrity checks",
    )
    args = parser.parse_args(argv)
    try:
        result = restore_backup(
            Path(args.backup), Path(args.destination), args.overwrite
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
