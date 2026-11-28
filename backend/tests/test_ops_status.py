"""Tests for the read-only /api/ops/status operational endpoint."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class OpsStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ops = Path(self.temp.name)
        (self.ops / "run").mkdir()
        (self.ops / "backups").mkdir()
        self.client = TestClient(app)

    def tearDown(self):
        self.temp.cleanup()

    def _get(self):
        with patch.dict(os.environ, {"MARKET_MIND_OPS_DIR": str(self.ops)}):
            # Auth disabled in tests: the operator guard is a no-op then.
            return self.client.get("/api/ops/status")

    def test_reports_services_and_boundaries_without_secrets(self):
        (self.ops / "run" / "backend.pid").write_text(str(os.getpid()))
        response = self._get()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("services", payload)
        self.assertIn("backend", payload["services"])
        self.assertTrue(payload["services"]["backend"]["running"])
        self.assertFalse(payload["execution"]["paper_trading"])
        self.assertFalse(payload["execution"]["broker_execution"])
        self.assertFalse(payload["secret_values_exposed"])

    def test_missing_pid_file_is_reported_as_not_running(self):
        payload = self._get().json()
        self.assertFalse(payload["services"]["supervisor"]["running"])
        self.assertIsNone(payload["services"]["supervisor"]["pid"])

    def test_stale_pid_is_not_reported_running(self):
        # A pid that cannot exist on this host.
        (self.ops / "run" / "proxy.pid").write_text("2147483646")
        payload = self._get().json()
        self.assertFalse(payload["services"]["proxy"]["running"])

    def test_invalid_pid_values_are_not_reported_running(self):
        for value in ("-1", "2147483648", "0", "not-a-pid"):
            (self.ops / "run" / "supervisor.pid").write_text(value)
            payload = self._get().json()
            self.assertFalse(payload["services"]["supervisor"]["running"], value)
            self.assertIsNone(payload["services"]["supervisor"]["pid"], value)
        # No 500 from an out-of-range lock PID either.
        (self.ops / "run" / "supervisor-loop.lock").write_text("2147483648")
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["supervision_loop_pid"])

    def test_backup_status_file_is_summarized(self):
        record = {
            "status": "verified",
            "run_at": "2026-01-01T00:00:00+00:00",
            "restore_test": {"status": "verified"},
        }
        (self.ops / "backups" / "scheduler-status.json").write_text(json.dumps(record))
        payload = self._get().json()
        self.assertEqual(payload["backups"]["status"], "verified")
        self.assertTrue(payload["backups"]["restore_verified"])

    def test_unreadable_backup_status_does_not_raise(self):
        (self.ops / "backups" / "scheduler-status.json").write_text("{not json")
        payload = self._get().json()
        self.assertEqual(payload["backups"]["status"], "unreadable")

    def test_no_command_execution_symbols_used(self):
        source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text()
        start = source.index("def ops_status")
        body = source[start:start + 4000]
        for forbidden in ("subprocess", "os.system", "popen", "shutil.copy"):
            self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
