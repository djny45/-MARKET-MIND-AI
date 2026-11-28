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
    "scripts/backup_scheduler.py",
    "scripts/service_restart_recovery.py",
    "scripts/docker_volume_drill.py",
    "scripts/install_schedule.py",
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
        # Isolate from any DR variables exported on the host; this test checks
        # the copied files, not the operator's environment.
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("MARKET_MIND_") and "SECRET" not in key
               and "TOKEN" not in key and "PASSWORD" not in key}
        env["DUMMY_SECRET_FOR_PREFLIGHT"] = "do-not-print-this-value"
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

    def test_host_networking_privilege_and_new_ports_are_rejected(self):
        compose = self.root / "docker-compose.yml"
        text = compose.read_text().replace(
            "  backend:\n    build:",
            "  backend:\n    network_mode: host\n    privileged: true\n"
            "    cap_add:\n      - SYS_ADMIN\n    ports:\n      - \"0.0.0.0:9000:9000\"\n    build:",
        )
        compose.write_text(text, encoding="utf-8")
        report = json.loads(self._run().stdout)
        for check in ("backend_not_host_published", "services_unprivileged",
                      "published_ports_loopback"):
            self.assertIn(check, report["failed"])

    def test_drift_in_audited_install_schedule_is_detected(self):
        schedule = self.root / "scripts" / "install_schedule.py"
        source = schedule.read_text()
        schedule.write_text(source.replace("_environment_directive(env_file)", "'# removed'"), encoding="utf-8")
        report = json.loads(self._run().stdout)
        self.assertIn("host_schedule_plan_valid", report["failed"])

    def test_missing_host_tooling_is_reported(self):
        (self.root / "scripts" / "service_restart_recovery.py").unlink()
        report = json.loads(self._run().stdout)
        self.assertIn("host_tooling_scripts_present", report["failed"])

    def test_ipv6_loopback_binding_is_accepted(self):
        compose = self.root / "docker-compose.yml"
        compose.write_text(
            compose.read_text().replace('"127.0.0.1:8080:8080"', '"[::1]:8080:8080"'),
            encoding="utf-8",
        )
        report = json.loads(self._run().stdout)
        self.assertNotIn("published_ports_loopback", report["failed"])

    def test_ingest_limits_must_be_applied_not_only_declared(self):
        server = self.root / "frontend" / "nginx.conf"
        server.write_text(
            server.read_text().replace("limit_req zone=market_mind_api burst=20 nodelay", ""),
            encoding="utf-8",
        )
        report = json.loads(self._run().stdout)
        self.assertIn("ingress_limits_and_proto", report["failed"])


if __name__ == "__main__":
    unittest.main()
