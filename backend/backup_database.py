"""Create and verify an atomic SQLite backup of the research database."""

import argparse
import json
import hashlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


def _integrity(path: Path) -> tuple[bool, str]:
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as connection:
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


def create_backup(source: Path, destination: Path, overwrite: bool = False) -> dict:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if source == destination:
        raise ValueError("source_and_destination_must_differ")
    if not source.is_file():
        raise FileNotFoundError("source_database_not_found")
    if destination.exists() and not overwrite:
        raise FileExistsError("destination_exists_use_overwrite")
    source_ok, source_status = _integrity(source)
    if not source_ok:
        raise ValueError("source_database_integrity_failed:" + source_status)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=destination.name + ".", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db:
            with sqlite3.connect(temporary_path) as backup_db:
                source_db.backup(backup_db)
        backup_ok, backup_status = _integrity(temporary_path)
        if not backup_ok:
            raise ValueError("backup_integrity_failed:" + backup_status)
        if destination.exists() and not overwrite:
            raise FileExistsError("destination_exists_use_overwrite")
        os.replace(temporary_path, destination)
        temporary_path = None
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return {
            "status": "verified",
            "sha256": digest,
            "source": source.name,
            "backup": str(destination),
            "bytes": destination.stat().st_size,
            "source_integrity": source_status,
            "backup_integrity": backup_status,
        }
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Back up and verify the MARKET-MIND SQLite database.")
    parser.add_argument("destination", help="New backup file path")
    parser.add_argument("--source", default=os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing destination after successful verification")
    args = parser.parse_args(argv)
    try:
        result = create_backup(Path(args.source), Path(args.destination), args.overwrite)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
