"""Interrupted recovery runs must be visible in the aggregated evidence."""
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
import service_restart_recovery  # noqa: E402
from dr_common import DrError, read_json  # noqa: E402
from service_restart_recovery import RecoveryConfig, run_recovery  # noqa: E402


class RecoveryJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.db = self.root / "market.db"
        with sqlite3.connect(self.db) as connection:
            connection.execute("CREATE TABLE market_bars (symbol TEXT)")
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
            )
            connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01')")
        self.config = RecoveryConfig(argparse.Namespace(
            db=self.db, state_dir=self.state, stale_after_seconds=900,
            skip_task_recovery=False,
        ))

    def test_interrupted_and_successful_runs_leave_distinct_journal_states(self):
        with patch.object(service_restart_recovery, "requeue_interrupted_tasks",
                          side_effect=DrError("injected_requeue_failure")):
            with self.assertRaises(DrError):
                run_recovery(self.config)
        journal = read_json(self.state / "recovery-journal.json")
        self.assertEqual(journal["status"], "failed")
        failed_reports = list(self.state.glob("restart-recovery-*.json"))
        self.assertTrue(any(json.loads(p.read_text())["status"] == "failed"
                            for p in failed_reports))
        report = recovery_report.build_report(self.root, self.state)
        self.assertTrue(report["sections"]["restart"]["interrupted_previous_run"])

        payload = {"status": "ok", "recovery": {"requeued_interrupted_count": 0}}
        with patch.object(service_restart_recovery, "requeue_interrupted_tasks",
                          return_value=payload):
            success = run_recovery(self.config)
        self.assertEqual(success["status"], "recovered")
        journal = read_json(self.state / "recovery-journal.json")
        self.assertEqual(journal["status"], "completed")
        report = recovery_report.build_report(self.root, self.state)
        self.assertFalse(report["sections"]["restart"]["interrupted_previous_run"])


if __name__ == "__main__":
    unittest.main()
