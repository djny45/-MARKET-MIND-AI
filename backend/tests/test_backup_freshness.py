"""Backup staleness reporting on `GET /api/backup/status`.

The endpoint used to return a constant `"status": "ok"`, so a backup schedule
that silently stopped (stuck lock, broken cron, disk full) looked healthy
forever — the same class of failure as the recycled-PID lock bug.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.main import _backup_max_age_seconds, backup_status


class BackupFreshnessTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.directory = Path(self._dir.name)
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_BACKUP_DIR": str(self.directory),
            "MARKET_MIND_BACKUP_MAX_AGE_SECONDS": "90000",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self._dir.cleanup()

    def _backup(self, name: str = "market_mind-20260101T000000Z.db", age_seconds: int = 0) -> Path:
        path = self.directory / name
        path.write_bytes(b"-- backup --")
        if age_seconds:
            stamp = time.time() - age_seconds
            os.utime(path, (stamp, stamp))
        return path

    def test_never_run_is_reported_as_missing(self):
        result = backup_status(None)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["freshness"]["state"], "never_run")
        self.assertIsNone(result["freshness"]["newest_age_seconds"])
        self.assertEqual(result["backup_count"], 0)

    def test_recent_backup_is_ok(self):
        self._backup()
        result = backup_status(None)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["freshness"]["state"], "ok")
        self.assertEqual(result["freshness"]["newest_age_seconds"], 0)
        self.assertEqual(result["backup_count"], 1)

    def test_old_backup_is_stale(self):
        self._backup(age_seconds=200000)
        result = backup_status(None)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["freshness"]["state"], "stale")
        self.assertGreater(
            result["freshness"]["newest_age_seconds"],
            result["freshness"]["max_age_seconds"],
        )

    def test_threshold_is_configurable(self):
        self._backup(age_seconds=7200)
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MAX_AGE_SECONDS": "3600"}):
            self.assertEqual(backup_status(None)["status"], "stale")
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MAX_AGE_SECONDS": "86400"}):
            self.assertEqual(backup_status(None)["status"], "ok")

    def test_invalid_threshold_falls_back_to_the_default(self):
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MAX_AGE_SECONDS": "not-a-number"}):
            self.assertEqual(_backup_max_age_seconds(), 90000)
        with patch.dict(os.environ, {"MARKET_MIND_BACKUP_MAX_AGE_SECONDS": "-5"}):
            self.assertEqual(_backup_max_age_seconds(), 90000)

    def test_newest_backup_wins_when_several_exist(self):
        self._backup(name="market_mind-20250101T000000Z.db", age_seconds=300000)
        self._backup(name="market_mind-20260101T000000Z.db", age_seconds=60)
        result = backup_status(None)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backup_count"], 2)
        self.assertLess(result["freshness"]["newest_age_seconds"], 600)

    def test_status_does_not_leak_database_paths(self):
        self._backup()
        with patch.dict(os.environ, {"MARKET_MIND_DB": "/tmp/secret/market.db"}):
            result = backup_status(None)
        self.assertNotIn("MARKET_MIND_DB", str(result))
        self.assertNotIn("/tmp/secret", str(result))


if __name__ == "__main__":
    unittest.main()
