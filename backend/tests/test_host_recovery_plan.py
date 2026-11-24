"""Host recovery planning must stay read-only and secret-free."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "host_recovery_plan.py"
sys.path.insert(0, str(ROOT / "scripts"))

import host_recovery_plan  # noqa: E402


def _clean_env(*extra: dict) -> dict:
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("MARKET_MIND_") and "SECRET" not in key
           and "TOKEN" not in key and "PASSWORD" not in key}
    for item in extra:
        env.update(item)
    return env


class HostRecoveryPlanTests(unittest.TestCase):
    def test_plan_aggregates_safe_sections(self):
        with patch.dict(os.environ, _clean_env(), clear=True):
            report = host_recovery_plan.build_plan(ROOT)
        self.assertEqual(report["status"], "prepared")
        self.assertEqual(report["preflight"]["status"], "pass")
        self.assertEqual(report["docker_volume"]["command_count"], 5)
        self.assertIn("systemctl", report["schedule"]["commands_not_run"])
        self.assertEqual(len(report["manual_steps"]), 5)
        self.assertTrue(report["rollback"])
        self.assertFalse(report["values_exposed"])

    def test_failed_preflight_blocks_preparation(self):
        with patch("config_preflight.build_report", return_value={
            "status": "fail", "failed": ["tls_template"],
        }):
            report = host_recovery_plan.build_plan(ROOT)
        self.assertEqual(report["status"], "preflight_failed")
        self.assertEqual(report["preflight"]["failed"], ["tls_template"])

    def test_cli_runs_no_privileged_commands_and_hides_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            log = Path(tmp) / "commands.log"
            for name in ("systemctl", "crontab", "docker"):
                shim = bin_dir / name
                shim.write_text(f"#!/bin/sh\necho {name} >> {shlex.quote(str(log))}\n")
                shim.chmod(0o755)
            env = _clean_env({"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                              "DUMMY_SECRET_FOR_PLAN": "do-not-print-this"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(ROOT)],
                env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "prepared")
            self.assertFalse(log.exists())
            self.assertNotIn("do-not-print-this", result.stdout)


if __name__ == "__main__":
    unittest.main()
