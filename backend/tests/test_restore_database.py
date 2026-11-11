import sqlite3
import tempfile
import unittest
from pathlib import Path

from restore_database import restore_backup


class DatabaseRestoreTests(unittest.TestCase):
    def _database(self, path, symbol="ETHUSD"):
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE market_bars (symbol TEXT)")
            connection.execute("INSERT INTO market_bars VALUES (?)", (symbol,))

    def test_restores_and_verifies_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.db"
            target = Path(directory) / "restored" / "market.db"
            self._database(backup)
            result = restore_backup(backup, target)
            self.assertEqual(result["status"], "restored_and_verified")
            self.assertEqual(result["backup_integrity"], "ok")
            self.assertEqual(result["restored_integrity"], "ok")
            self.assertEqual(len(result["sha256"]), 64)
            with sqlite3.connect(target) as connection:
                self.assertEqual(
                    connection.execute("SELECT symbol FROM market_bars").fetchone()[0],
                    "ETHUSD",
                )

    def test_refuses_to_overwrite_existing_target_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.db"
            target = Path(directory) / "target.db"
            self._database(backup)
            target.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "destination_exists"):
                restore_backup(backup, target)
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve")

    def test_rejects_invalid_backup_without_changing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "bad.db"
            target = Path(directory) / "target.db"
            backup.write_text("not a sqlite database", encoding="utf-8")
            target.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "backup_integrity_failed"):
                restore_backup(backup, target, overwrite=True)
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve")

    def test_requires_explicit_overwrite_and_replaces_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.db"
            target = Path(directory) / "target.db"
            self._database(backup, "SOLUSD")
            self._database(target, "OLD")
            result = restore_backup(backup, target, overwrite=True)
            self.assertEqual(result["status"], "restored_and_verified")
            with sqlite3.connect(target) as connection:
                self.assertEqual(
                    connection.execute("SELECT symbol FROM market_bars").fetchone()[0],
                    "SOLUSD",
                )

    def test_refuses_same_backup_and_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.db"
            self._database(backup)
            with self.assertRaisesRegex(ValueError, "backup_and_destination_must_differ"):
                restore_backup(backup, backup)

    def test_restores_database_from_path_with_uri_reserved_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            unusual_directory = Path(directory) / "backup #? directory"
            unusual_directory.mkdir()
            backup = unusual_directory / "market #?.db"
            target = Path(directory) / "restored #?.db"
            self._database(backup, "BTCUSD")

            result = restore_backup(backup, target)

            self.assertEqual(result["status"], "restored_and_verified")
            with sqlite3.connect(target) as connection:
                self.assertEqual(
                    connection.execute("SELECT symbol FROM market_bars").fetchone()[0],
                    "BTCUSD",
                )


if __name__ == "__main__":
    unittest.main()
