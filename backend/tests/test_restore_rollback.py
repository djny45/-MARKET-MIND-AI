"""A failed restore must roll back an overwritten target and leave evidence."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import restore_orchestrator  # noqa: E402
from backup_orchestrator import BackupConfig, run_backup  # noqa: E402
from dr_common import DrError  # noqa: E402
from restore_orchestrator import RestoreConfig, restore_backup  # noqa: E402


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE market_bars (symbol TEXT)")
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01')")
    return path


class RestoreRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = _database(self.root / "source.db")
        backup_args = argparse.Namespace(
            source=self.source, destination_dir=self.root / "backups",
            state_dir=self.root / "backup-state", retention_days=30,
            retention_count=None, upload_command="", backup=None,
            dry_run=False, alert_on_success=False,
        )
        self.backup = Path(run_backup(BackupConfig(backup_args))["backup"])
        self.target = self.root / "target"
        self.target.mkdir()
        self.original = self.target / "market_mind.db"
        self.original.write_bytes(b"ORIGINAL-LIVE-DATABASE")
        self.restore_args = argparse.Namespace(
            backup=self.backup, target=self.target,
            state_dir=self.root / "restore-state", overwrite=True,
            expect_sha256=None, no_strict_compare=False, alert_on_success=False,
        )

    def test_injected_copy_failure_restores_the_original_target(self):
        def fail(config, destination):
            destination.write_bytes(b"PARTIAL-CORRUPT")
            return {"status": "failed"}

        with patch.object(restore_orchestrator, "_restore_copy", side_effect=fail):
            with self.assertRaises(DrError):
                restore_backup(RestoreConfig(self.restore_args))
        self.assertEqual(self.original.read_bytes(), b"ORIGINAL-LIVE-DATABASE")
        reports = list((self.root / "restore-state").glob("restore-report-*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["rollback"]["status"], "restored")

    def test_wal_committed_data_survives_a_failed_restore(self):
        self.original.write_bytes(b"")  # start from a valid empty SQLite file
        connection = sqlite3.connect(self.original, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE live (id INTEGER)")
        connection.execute("INSERT INTO live VALUES (1)")
        self.assertTrue((self.root / "target" / "market_mind.db-wal").exists())

        def fail(config, destination):
            destination.write_bytes(b"PARTIAL-CORRUPT")
            return {"status": "failed"}

        with patch.object(restore_orchestrator, "_restore_copy", side_effect=fail):
            with self.assertRaises(DrError):
                restore_backup(RestoreConfig(self.restore_args))
        connection.close()
        # The rollback must leave no stale sidecars from the failed restore;
        # a later read may legitimately recreate WAL files for a WAL-mode DB.
        self.assertFalse(Path(str(self.original) + "-wal").exists())
        self.assertFalse(Path(str(self.original) + "-shm").exists())
        with sqlite3.connect(self.original) as check:
            self.assertEqual(check.execute("SELECT COUNT(*) FROM live").fetchone()[0], 1)
        reports = list((self.root / "restore-state").glob("restore-report-*.json"))
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text())["status"], "failed")

    def test_successful_overwrite_records_the_snapshot(self):
        result = restore_backup(RestoreConfig(self.restore_args))
        self.assertEqual(result["status"], "restored_and_verified")
        snapshot = Path(result["rollback_snapshot"])
        self.assertEqual(snapshot.read_bytes(), b"ORIGINAL-LIVE-DATABASE")
        self.assertTrue(snapshot.with_name(snapshot.name + ".sha256").is_file())


if __name__ == "__main__":
    unittest.main()
