import sqlite3
import tempfile
import unittest
from pathlib import Path

from backup_database import create_backup


class DatabaseBackupTests(unittest.TestCase):
    def _database(self, path):
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE market_bars (symbol TEXT)")
            connection.execute("INSERT INTO market_bars VALUES ('BTCUSD')")

    def test_creates_and_verifies_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "market.db"
            destination = Path(directory) / "backups" / "market-copy.db"
            self._database(source)
            result = create_backup(source, destination)
            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["source_integrity"], "ok")
            self.assertEqual(result["backup_integrity"], "ok")
            with sqlite3.connect(destination) as connection:
                self.assertEqual(connection.execute("SELECT symbol FROM market_bars").fetchone()[0], "BTCUSD")

    def test_refuses_to_overwrite_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "market.db"
            destination = Path(directory) / "backup.db"
            self._database(source)
            destination.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "destination_exists"):
                create_backup(source, destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep")

    def test_refuses_same_source_and_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "market.db"
            self._database(source)
            with self.assertRaisesRegex(ValueError, "source_and_destination_must_differ"):
                create_backup(source, source)

    def test_rejects_database_without_market_bars_table(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "empty.db"
            with sqlite3.connect(source):
                pass
            with self.assertRaisesRegex(ValueError, "market_bars_table_missing"):
                create_backup(source, Path(directory) / "backup.db")

    def test_overwrite_replaces_only_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "market.db"
            destination = Path(directory) / "backup.db"
            self._database(source)
            destination.write_text("old", encoding="utf-8")
            result = create_backup(source, destination, overwrite=True)
            self.assertEqual(result["status"], "verified")
            with sqlite3.connect(destination) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
