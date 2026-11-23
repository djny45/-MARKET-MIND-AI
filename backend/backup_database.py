"""Create and verify an atomic SQLite backup of the research database."""

import argparse
import json
import hashlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


def _readonly_database_uri(path: Path) -> str:
    """Build a correctly escaped SQLite file URI for read-only access."""
    return path.resolve().as_uri() + "?mode=ro"


SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _remove_sidecars(path: Path) -> None:
    """Remove SQLite WAL/journal sidecars that belong to ``path``.

    ``Connection.backup`` from a WAL source switches the destination to WAL
    mode, so the copy leaves ``-wal``/``-shm`` files behind. The artifact must
    be a single self-contained file: they would otherwise accumulate in the
    backup directory on every run and never be pruned.
    """
    for suffix in SIDECAR_SUFFIXES:
        sidecar = Path(str(path) + suffix)
        try:
            sidecar.unlink(missing_ok=True)
        except OSError:
            pass


def _close_quietly(connection: sqlite3.Connection | None) -> None:
    """Close a connection so SQLite checkpoints and drops its WAL files."""
    if connection is None:
        return
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.Error:
        pass
    try:
        connection.close()
    except sqlite3.Error:
        pass


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
        source_db = None
        backup_db = None
        try:
            source_db = sqlite3.connect(_readonly_database_uri(source), uri=True)
            backup_db = sqlite3.connect(temporary_path)
            source_db.backup(backup_db)
        finally:
            # Closing checkpoints the copy's WAL back into the database file so
            # the artifact is a single file rather than a file plus sidecars.
            _close_quietly(backup_db)
            _close_quietly(source_db)
        backup_ok, backup_status = _integrity(temporary_path)
        if not backup_ok:
            raise ValueError("backup_integrity_failed:" + backup_status)
        if destination.exists() and not overwrite:
            raise FileExistsError("destination_exists_use_overwrite")
        os.replace(temporary_path, destination)
        temporary_path = None
        _remove_sidecars(destination)
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
        if temporary_path:
            _remove_sidecars(temporary_path)


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
