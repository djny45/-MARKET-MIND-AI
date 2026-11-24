"""Host schedule scaffolding is dry-run-first and never installs anything itself."""
from __future__ import annotations

import json
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

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=30,
        )

    def test_plan_writes_nothing_and_runs_no_privileged_commands(self):
        result = self._run("plan", "--output-dir", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "planned")
        self.assertFalse(self.output.exists())
        self.assertEqual(payload["commands_not_run"], ["systemctl", "crontab", "systemctl enable"])
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)

    def test_generated_units_have_expected_safety_fields(self):
        payload = json.loads(self._run("plan", "--output-dir", str(self.output)).stdout)
        files = payload["files"]
        self.assertIn("Type=oneshot", files["market-mind-backup.service"])
        self.assertIn("Type=oneshot", files["market-mind-restart-recovery.service"])
        self.assertIn("Persistent=true", files["market-mind-backup.timer"])
        self.assertIn("WantedBy=timers.target", files["market-mind-backup.timer"])
        self.assertIn("EnvironmentFile=", files["market-mind-backup.service"])
        self.assertIn("0600", files["market-mind-restart-recovery.service"])
        self.assertNotIn("MARKET_MIND_S3_SECRET_KEY=", "".join(files.values()))

    def test_invalid_cron_schedule_fails_closed(self):
        result = self._run("plan", "--output-dir", str(self.output), "--schedule", "invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cron_schedule_must_have_5_fields", result.stdout)

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
        result = self._run("apply", "--apply", "--output-dir", "/etc/systemd/system")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("system_path_requires_allow_system_paths", result.stdout)
        self.assertFalse(Path("/etc/systemd/system/market-mind-backup.service").exists())


if __name__ == "__main__":
    unittest.main()
