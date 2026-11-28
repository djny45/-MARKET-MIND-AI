"""Backup orchestration fails closed before copying onto a full volume."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import backup_orchestrator  # noqa: E402
from backup_orchestrator import BackupConfig, run_backup  # noqa: E402
from dr_common import DrError, atomic_write_json  # noqa: E402


class DrStorageFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.db"
        with sqlite3.connect(self.source) as connection:
            connection.execute("CREATE TABLE market_bars (symbol TEXT)")
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
            )
            connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01')")
        self.args = argparse.Namespace(
            source=self.source, destination_dir=self.root / "backups",
            state_dir=self.root / "state", retention_days=30, retention_count=None,
            upload_command="", backup=None, dry_run=False, alert_on_success=False,
        )

    def test_low_free_space_aborts_before_creating_a_backup(self):
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MIN_FREE_MB": "500"}), \
             patch.object(backup_orchestrator.shutil, "disk_usage",
                          return_value=SimpleNamespace(free=2 * 1024 * 1024)):
            with self.assertRaises(DrError) as caught:
                run_backup(BackupConfig(self.args))
        self.assertIn("insufficient_backup_disk_space", str(caught.exception))
        self.assertEqual(list((self.root / "backups").glob("*.db")), [])

    def test_probe_failure_is_reported_not_ignored(self):
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MIN_FREE_MB": "500"}), \
             patch.object(backup_orchestrator.shutil, "disk_usage", side_effect=OSError("probe")):
            with self.assertRaises(DrError) as caught:
                run_backup(BackupConfig(self.args))
        self.assertIn("backup_disk_probe_failed", str(caught.exception))

    def test_resume_of_non_copy_phases_skips_the_disk_probe(self):
        config = BackupConfig(self.args)
        config.state_dir.mkdir(parents=True, exist_ok=True)
        config.destination_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(config.state_dir / "backup-journal.json", {
            "status": "in_progress", "phase": "prune",
            "backup": "market_mind-test.db", "sha256": "a" * 64, "backup_bytes": 1,
            "upload": {"status": "uploaded"},
        })
        (config.destination_dir / "market_mind-test.db").write_bytes(b"x")
        with patch.object(backup_orchestrator, "_ensure_free_space",
                          side_effect=AssertionError("probe must be skipped on resume")):
            result = run_backup(config, resume=True)
        self.assertEqual(result["status"], "completed")

    def test_default_configuration_does_not_require_a_disk_probe(self):
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MIN_FREE_MB": ""}), \
             patch.object(backup_orchestrator.shutil, "disk_usage",
                          side_effect=AssertionError("probe must be skipped")):
            result = run_backup(BackupConfig(self.args))
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
