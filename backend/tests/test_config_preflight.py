"""Offline deployment preflight must detect drift without leaking configuration."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "config_preflight.py"
FILES = (
    "deploy/tls/nginx-tls.conf.example",
    "frontend/nginx-limits.conf",
    "frontend/nginx.conf",
    "frontend/Dockerfile",
    "docker-compose.yml",
    "scripts/deploy_check.sh",
)


class ConfigPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        for relative in FILES:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def _run(self, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            env=env or dict(os.environ), capture_output=True, text=True, timeout=30,
        )

    def test_clean_configuration_passes_without_exposing_values(self):
        env = dict(os.environ, DUMMY_SECRET_FOR_PREFLIGHT="do-not-print-this-value")
        result = self._run(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failed"], [])
        self.assertFalse(report["values_exposed"])
        self.assertNotIn("do-not-print-this-value", result.stdout)

    def test_tls_and_compose_drift_are_detected(self):
        tls = self.root / FILES[0]
        tls.write_text(tls.read_text().replace("Strict-Transport-Security", "Removed"), encoding="utf-8")
        compose = self.root / "docker-compose.yml"
        compose.write_text(compose.read_text().replace(
            "  backend:\n    build:", "  backend:\n    ports:\n      - \"8000:8000\"\n    build:"
        ), encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertIn("tls_template", report["failed"])
        self.assertIn("backend_not_host_published", report["failed"])
        self.assertIn("published_ports_loopback", report["failed"])

    def test_missing_tls_template_fails_without_crashing(self):
        (self.root / FILES[0]).unlink()
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tls_template", json.loads(result.stdout)["failed"])

    def test_invalid_dr_environment_is_reported_without_values(self):
        env = dict(os.environ, MARKET_MIND_BACKUP_RETENTION_DAYS="not-a-number",
                   MARKET_MIND_INCIDENT_WEBHOOK_URL="https://ops.invalid/hook?token=abc123")
        result = self._run(env)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertIn("dr_environment", report["failed"])
        self.assertNotIn("not-a-number", result.stdout)
        self.assertNotIn("abc123", result.stdout)


if __name__ == "__main__":
    unittest.main()
