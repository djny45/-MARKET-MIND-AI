"""A failed off-host upload must never be finalized by a later resume."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from backup_orchestrator import BackupConfig, run_backup  # noqa: E402
from dr_common import DrError, DrInterrupted, read_json  # noqa: E402


class FailedUploadResumeTests(unittest.TestCase):
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
        self.hook = self.root / "failing_hook.py"
        self.hook.write_text("raise SystemExit(7)\n", encoding="utf-8")
        self.args = argparse.Namespace(
            source=self.source, destination_dir=self.root / "backups",
            state_dir=self.root / "state", retention_days=30, retention_count=None,
            upload_command=f"{sys.executable} {self.hook} {{backup}}", backup=None,
            dry_run=False, alert_on_success=False,
        )
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "",
            "MARKET_MIND_DR_ALERT_ON_SUCCESS": "false",
            "MARKET_MIND_BACKUP_KEEP": "",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_resume_does_not_finalize_a_failed_upload(self):
        with self.assertRaises(DrError) as caught:
            run_backup(BackupConfig(self.args))
        self.assertIn("offhost_upload_failed", str(caught.exception))
        journal = read_json(self.root / "state" / "backup-journal.json")
        self.assertNotEqual(journal.get("phase"), "prune")
        self.assertNotEqual(journal.get("status"), "completed")
        with self.assertRaises(DrError) as resumed:
            run_backup(BackupConfig(self.args), resume=True)
        self.assertIn("offhost_upload_failed", str(resumed.exception))
        journal = read_json(self.root / "state" / "backup-journal.json")
        self.assertNotEqual(journal.get("status"), "completed")


if __name__ == "__main__":
    unittest.main()
