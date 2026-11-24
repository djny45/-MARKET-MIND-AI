"""Aggregated recovery evidence must be reproducible from real local artifacts."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
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
        self._create_valid_artifacts()
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

    def test_present_but_invalid_artifacts_are_not_counted_as_evidence(self):
        source = _database(self.root / "market_mind-invalid.db")
        (self.root / "market_mind-invalid.db.json").write_text('{"integrity": "failed"}')
        (self.root / "restore-report-invalid.json").write_text('{"status": "failed", "comparison": {}}')
        (self.root / "restart-recovery-invalid.json").write_text('{"status": "failed"}')
        report = recovery_report.build_report(self.root)
        self.assertEqual(report["status"], "evidence_incomplete")
        self.assertFalse(report["sections"]["backup"]["evidence_valid"])
        self.assertFalse(report["sections"]["restore"]["evidence_valid"])
        self.assertFalse(report["sections"]["restart"]["evidence_valid"])

    def test_interrupted_recovery_journal_blocks_complete_evidence(self):
        self._create_valid_artifacts()
        (self.root / "recovery-journal.json").write_text(
            json.dumps({"status": "in_progress", "phase": "requeue"}), encoding="utf-8"
        )
        report = recovery_report.build_report(self.root)
        self.assertEqual(report["status"], "evidence_incomplete")
        self.assertTrue(report["sections"]["restart"]["interrupted_previous_run"])
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "recovery_report.py"),
             "--root", str(self.root)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_restore_report_for_an_older_backup_is_not_complete_evidence(self):
        self._create_valid_artifacts()
        original = next(self.root.glob("market_mind-*.db"))
        newer = self.root / "market_mind-20990101T000000Z.db"
        shutil.copy2(original, newer)
        shutil.copy2(Path(str(original) + ".json"), Path(str(newer) + ".json"))
        stamp = time.time() + 1000
        os.utime(newer, (stamp, stamp))
        report = recovery_report.build_report(self.root)
        self.assertEqual(report["status"], "evidence_incomplete")
        self.assertFalse(report["sections"]["restore"]["paired_to_newest_backup"])

    def test_cli_exits_non_zero_for_incomplete_evidence(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "recovery_report.py"),
             "--root", str(self.root)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "evidence_incomplete")

    def test_reports_in_the_default_state_directory_are_found(self):
        self._create_valid_artifacts()
        state = self.root / ".state"
        state.mkdir(exist_ok=True)
        for path in self.root.glob("restore-report-*.json"):
            path.rename(state / path.name)
        for path in self.root.glob("restart-recovery-*.json"):
            path.rename(state / path.name)
        report = recovery_report.build_report(self.root)
        self.assertEqual(report["status"], "evidence_complete")
        self.assertTrue(report["sections"]["restore"]["report"].startswith(str(state)))

    def _create_valid_artifacts(self):
        backup_args = argparse.Namespace(
            source=self.source, destination_dir=self.root, state_dir=self.root,
            retention_days=30, retention_count=None, upload_command="",
            backup=None, dry_run=False, alert_on_success=False,
        )
        backup = run_backup(BackupConfig(backup_args))
        restore_args = argparse.Namespace(
            backup=Path(backup["backup"]), target=self.root / "restored",
            state_dir=self.root, overwrite=True, expect_sha256=None,
            no_strict_compare=False, alert_on_success=False,
        )
        restore_backup(RestoreConfig(restore_args))
        recovery_args = argparse.Namespace(
            db=self.source, state_dir=self.root, stale_after_seconds=900,
            skip_task_recovery=True,
        )
        run_recovery(RecoveryConfig(recovery_args))


if __name__ == "__main__":
    unittest.main()
