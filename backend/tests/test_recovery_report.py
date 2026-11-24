"""Aggregated recovery evidence must be reproducible from real local artifacts."""
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

import recovery_report  # noqa: E402
from backup_orchestrator import BackupConfig, run_backup  # noqa: E402
from restore_orchestrator import RestoreConfig, restore_backup  # noqa: E402
from service_restart_recovery import RecoveryConfig, run_recovery  # noqa: E402


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE market_bars (symbol TEXT, interval TEXT, timestamp TEXT, "
            "open REAL, high REAL, low REAL, close REAL, volume REAL, status TEXT, "
            "source TEXT, retrieved_at TEXT)"
        )
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')")
    return path


class RecoveryReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "artifacts"
        self.root.mkdir()
        self.source = _database(Path(self.temp.name) / "source.db")
        self.env = patch.dict("os.environ", {
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "",
            "MARKET_MIND_DR_ALERT_ON_SUCCESS": "false",
            "MARKET_MIND_BACKUP_KEEP": "",
            "MARKET_MIND_BACKUP_MAX_AGE_SECONDS": "90000",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_report_aggregates_real_backup_restore_and_restart_artifacts(self):
        backup_args = argparse.Namespace(
            source=self.source, destination_dir=self.root, state_dir=self.root,
            retention_days=30, retention_count=None, upload_command=None,
            backup=None, dry_run=False, alert_on_success=False,
        )
        backup = run_backup(BackupConfig(backup_args))
        self.assertEqual(backup["status"], "completed")

        restore_args = argparse.Namespace(
            backup=Path(backup["backup"]), target=self.root / "restored",
            state_dir=self.root, overwrite=True, expect_sha256=None,
            no_strict_compare=False, alert_on_success=False,
        )
        restored = restore_backup(RestoreConfig(restore_args))
        self.assertEqual(restored["comparison"]["status"], "matched")

        recovery_args = argparse.Namespace(
            db=self.source, state_dir=self.root, stale_after_seconds=900,
            skip_task_recovery=True,
        )
        recovery = run_recovery(RecoveryConfig(recovery_args))
        self.assertEqual(recovery["status"], "recovered")

        report = recovery_report.build_report(self.root)
        self.assertEqual(report["status"], "evidence_complete")
        self.assertEqual(report["sections"]["backup"]["count"], 1)
        self.assertEqual(report["sections"]["backup"]["freshness"], "ok")
        self.assertEqual(report["sections"]["backup"]["integrity"], "ok")
        self.assertEqual(report["sections"]["restore"]["status"], "restored_and_verified")
        self.assertEqual(report["sections"]["restore"]["comparison"], "matched")
        self.assertEqual(report["sections"]["restart"]["status"], "recovered")
        self.assertEqual(report["sections"]["restart"]["stale_locks_removed"], 0)
        self.assertFalse(report["values_exposed"])
        self.assertNotIn(str(self.source), json.dumps(report))

    def test_missing_artifacts_are_reported_as_incomplete(self):
        report = recovery_report.build_report(self.root)
        self.assertEqual(report["status"], "evidence_incomplete")
        self.assertEqual(report["sections"]["backup"]["freshness"], "never_run")
        self.assertIsNone(report["sections"]["backup"]["newest_age_seconds"])
        self.assertIsNone(report["sections"]["restore"]["status"])


if __name__ == "__main__":
    unittest.main()
