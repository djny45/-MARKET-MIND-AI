"""Host schedule scaffolding is dry-run-first and never installs anything itself."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install_schedule.py"


class InstallScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "generated"

    def _run(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], env=env or dict(os.environ),
            capture_output=True, text=True, timeout=30,
        )

    def test_plan_writes_nothing_and_runs_no_privileged_commands(self):
        result = self._run("plan", "--output-dir", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "planned")
        self.assertFalse(self.output.exists())
        self.assertEqual(payload["commands_not_run"], ["systemctl", "crontab", "systemctl enable"])

        # Observe the actual command boundary with controlled executables.
        bin_dir = Path(self.temp.name) / "fake-bin"
        bin_dir.mkdir()
        log = Path(self.temp.name) / "privileged.log"
        for name in ("systemctl", "crontab"):
            shim = bin_dir / name
            shim.write_text(
                f"#!/bin/sh\necho {name} >> {shlex.quote(str(log))}\n", encoding="utf-8"
            )
            shim.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        self.assertEqual(self._run("plan", "--output-dir", str(self.output), env=env).returncode, 0)
        self.assertEqual(self._run("apply", "--apply", "--output-dir", str(self.output), env=env).returncode, 0)
        self.assertFalse(log.exists(), "systemctl/crontab must never be invoked")

    def test_generated_units_have_expected_safety_fields(self):
        payload = json.loads(self._run("plan", "--output-dir", str(self.output)).stdout)
        files = payload["files"]
        self.assertIn("Type=oneshot", files["market-mind-backup.service"])
        self.assertIn("Type=oneshot", files["market-mind-restart-recovery.service"])
        self.assertIn("OnCalendar=daily", files["market-mind-backup.timer"])
        self.assertIn("Persistent=true", files["market-mind-backup.timer"])
        self.assertIn("WantedBy=timers.target", files["market-mind-backup.timer"])
        for service in ("market-mind-backup.service", "market-mind-restart-recovery.service"):
            self.assertIn("\nEnvironmentFile=/etc/market-mind/market-mind.env\n", files[service])
        self.assertIn("\nWantedBy=multi-user.target", files["market-mind-restart-recovery.service"])
        self.assertIn(". /etc/market-mind/market-mind.env", files["market-mind-backup.cron"])
        self.assertNotIn("MARKET_MIND_S3_SECRET_KEY=", "".join(files.values()))

    def test_invalid_cron_schedule_fails_closed(self):
        result = self._run("plan", "--output-dir", str(self.output), "--schedule", "invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cron_schedule_must_have_5_fields", result.stdout)
        for bad in ("61 * * * *", "* 24 * * *", "*/0 * * * *", "0 0 32 * *"):
            result = self._run("plan", "--output-dir", str(self.output), "--schedule", bad)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cron_field_", result.stdout)
        good = self._run("plan", "--output-dir", str(self.output),
                         "--schedule", "*/5 0-6 1,15 * 1-5")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn("*/5 0-6 1,15 * 1-5", json.loads(good.stdout)["files"]["market-mind-backup.cron"])

    def test_invalid_calendar_expression_fails_closed(self):
        result = self._run("plan", "--output-dir", str(self.output), "--on-calendar", "   ")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("on_calendar_invalid", result.stdout)

    def test_apply_writes_only_to_the_chosen_output_directory(self):
        result = self._run("apply", "--apply", "--output-dir", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "written")
        for name in ("market-mind-backup.service", "market-mind-backup.timer",
                     "market-mind-restart-recovery.service", "market-mind-backup.cron",
                     "install-plan.json"):
            self.assertTrue((self.output / name).is_file(), name)
        self.assertFalse((Path(self.temp.name) / "market-mind-backup.service").exists())

    def test_apply_requires_explicit_opt_in_for_system_paths(self):
        for target in ("/etc/systemd/system", "/usr/local/lib/systemd/system", "/run/systemd/system"):
            result = self._run("apply", "--apply", "--output-dir", target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("system_path_requires_allow_system_paths", result.stdout)

    def test_apply_refuses_symlinked_output_targets(self):
        self.output.mkdir()
        outside = Path(self.temp.name) / "outside.service"
        outside.write_text("untouched", encoding="utf-8")
        link = self.output / "market-mind-backup.service"
        link.symlink_to(outside)
        result = self._run("apply", "--apply", "--output-dir", str(self.output))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing_symlinked_output", result.stdout)
        self.assertEqual(outside.read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()
