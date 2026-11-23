"""Backup/restore must leave one self-contained file behind, not WAL debris.

Copying a WAL-mode database with ``Connection.backup`` switches the copy to WAL
mode, which leaves ``-wal``/``-shm`` files next to the artifact. Retention prunes
only ``*.db``/``*.sha256``, so those sidecars would accumulate in the DR folder
forever and could be mistaken for part of a backup.
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.sqlite_tuning import connect
from backend.backup_database import create_backup
from backend.restore_database import restore_backup

SIDECARS = ("-wal", "-shm", "-journal")


def _sidecars(path: Path) -> list[str]:
    return [str(path) + suffix for suffix in SIDECARS if Path(str(path) + suffix).exists()]


def _make_database(path: Path, rows: int) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(path)
    connection.execute("CREATE TABLE market_bars (symbol TEXT PRIMARY KEY)")
    connection.executemany(
        "INSERT INTO market_bars VALUES (?)", [(f"ROW{index}",) for index in range(rows)]
    )
    connection.commit()
    return connection


class BackupWalHygieneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_of_live_wal_database_leaves_a_single_file(self):
        source = self.root / "live" / "market_mind.db"
        writer = _make_database(source, 5000)  # keep the connection open: WAL holds data
        try:
            self.assertTrue(_sidecars(source), "expected a live WAL before backing up")
            destination = self.root / "backup" / "market_mind.db"
            result = create_backup(source, destination)
        finally:
            writer.close()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(_sidecars(destination), [], "backup left WAL sidecars behind")
        leftovers = sorted(p.name for p in destination.parent.iterdir())
        self.assertEqual(leftovers, ["market_mind.db"])

    def test_backup_file_alone_contains_every_row(self):
        source = self.root / "live" / "market_mind.db"
        writer = _make_database(source, 2000)
        try:
            destination = self.root / "backup" / "market_mind.db"
            create_backup(source, destination)
        finally:
            writer.close()
        solo = self.root / "solo" / "market_mind.db"
        solo.parent.mkdir(parents=True)
        shutil.copyfile(destination, solo)  # deliberately drop any sidecar
        with sqlite3.connect(solo) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0], 2000
            )

    def test_restore_replaces_stale_wal_sidecars(self):
        source = self.root / "live" / "market_mind.db"
        writer = _make_database(source, 10)
        writer.close()
        backup = self.root / "backup" / "market_mind.db"
        create_backup(source, backup)

        # target left in WAL mode with its own sidecars present
        target = self.root / "restored" / "market_mind.db"
        stale = _make_database(target, 3)
        stale.execute("INSERT INTO market_bars VALUES ('STALE')")
        stale.commit()
        self.assertTrue(_sidecars(target))
        stale.close()

        result = restore_backup(backup, target, overwrite=True)
        self.assertEqual(result["status"], "restored_and_verified")
        self.assertEqual(_sidecars(target), [], "restore left stale WAL sidecars behind")
        with sqlite3.connect(target) as connection:
            rows = [row[0] for row in connection.execute("SELECT symbol FROM market_bars")]
        self.assertEqual(len(rows), 10)
        self.assertNotIn("STALE", rows)

    def test_restore_does_not_leave_temporary_sidecars(self):
        source = self.root / "live" / "market_mind.db"
        _make_database(source, 5).close()
        backup = self.root / "backup" / "market_mind.db"
        create_backup(source, backup)
        target = self.root / "restored" / "market_mind.db"
        restore_backup(backup, target)
        names = sorted(p.name for p in target.parent.iterdir())
        self.assertEqual(names, ["market_mind.db"])


if __name__ == "__main__":
    unittest.main()
