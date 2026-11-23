"""The tuned connection factory must apply, and keep applying, WAL settings."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import sqlite_tuning
from app.sqlite_tuning import applied_modes, connect, reset_cache

REPO_ROOT = Path(__file__).resolve().parents[2]


class SqliteTuningTests(unittest.TestCase):
    def setUp(self):
        sqlite_tuning.reset_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "tuned.db"

    def tearDown(self):
        self.tmp.cleanup()
        sqlite_tuning.reset_cache()

    def test_file_database_uses_wal_and_normal_synchronous(self):
        with connect(self.db) as connection:
            modes = applied_modes(connection)
        self.assertEqual(modes["journal_mode"], "wal")
        self.assertIn(modes["synchronous"], {"1", "normal"})
        self.assertGreaterEqual(int(modes["busy_timeout"]), 5000)

    def test_wal_is_persistent_for_later_connections(self):
        connect(self.db).close()
        reset_cache()  # simulate another process
        with connect(self.db) as connection:
            self.assertEqual(applied_modes(connection)["journal_mode"], "wal")

    def test_memory_database_is_left_on_memory_journal(self):
        connection = connect(":memory:")
        try:
            self.assertIn(applied_modes(connection)["journal_mode"], {"memory", "wal"})
            connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO t DEFAULT VALUES")
            self.assertEqual(connection.total_changes, 1)
        finally:
            connection.close()

    def test_wal_can_be_disabled_for_callers(self):
        connection = connect(self.db, wal=False)
        try:
            self.assertEqual(applied_modes(connection)["journal_mode"], "delete")
        finally:
            connection.close()

    def test_committed_rows_survive_reopen(self):
        with connect(self.db) as connection:
            connection.execute("CREATE TABLE t (value TEXT)")
            connection.execute("INSERT INTO t VALUES ('kept')")
            connection.commit()
        with connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT value FROM t").fetchone()[0], "kept")

    def test_online_backup_captures_rows_still_in_the_wal(self):
        from backend.backup_database import create_backup

        with connect(self.db) as connection:
            connection.execute(
                "CREATE TABLE market_bars (symbol TEXT NOT NULL, interval TEXT NOT NULL, "
                "timestamp TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, "
                "volume REAL, status TEXT, source TEXT, retrieved_at TEXT, "
                "PRIMARY KEY (symbol, interval, timestamp, source))"
            )
            connection.execute("CREATE TABLE t (value TEXT)")
            connection.execute("INSERT INTO t VALUES ('in-wal')")
            connection.commit()
        wal_file = Path(str(self.db) + "-wal")
        self.assertTrue(wal_file.exists() and wal_file.stat().st_size > 0,
                        "expected WAL content before checkpointing")
        destination = Path(self.tmp.name) / "backup.db"
        result = create_backup(self.db, destination)
        self.assertEqual(result["status"], "verified")
        with sqlite3.connect(destination) as copy:
            self.assertEqual(copy.execute("SELECT value FROM t").fetchone()[0], "in-wal")

    def test_application_modules_do_not_bypass_the_factory(self):
        offenders = []
        for path in sorted((REPO_ROOT / "backend" / "app").glob("*.py")):
            if path.name == "sqlite_tuning.py":
                continue
            if "sqlite3.connect(" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual(offenders, [], "use sqlite_tuning.connect for file databases")


if __name__ == "__main__":
    unittest.main()
