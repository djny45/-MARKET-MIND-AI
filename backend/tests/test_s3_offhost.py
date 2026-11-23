"""The S3 prerequisite must never expose credentials or claim a real restore."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "s3_offhost.py"


class S3OffhostTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(os.environ)
        self.env.update({
            "MARKET_MIND_S3_ENDPOINT": "https://s3.example.invalid",
            "MARKET_MIND_S3_BUCKET": "research-backups",
            "MARKET_MIND_S3_REGION": "us-east-1",
            "MARKET_MIND_S3_ACCESS_KEY": "DUMMYACCESSKEY",
            "MARKET_MIND_S3_SECRET_KEY": "DUMMYSECRETKEY-DO-NOT-USE",
            "MARKET_MIND_S3_PREFIX": "market-mind/backups",
        })

    def _run(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=env or self.env, capture_output=True, text=True, timeout=20,
        )

    def test_missing_credentials_fail_closed_without_printing_values(self):
        env = {k: v for k, v in self.env.items() if not k.startswith("MARKET_MIND_S3_")}
        result = self._run("describe-config", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing S3 environment variables", result.stderr)
        self.assertNotIn("DUMMYSECRETKEY", result.stdout + result.stderr)

    def test_describe_config_and_dry_run_expose_no_secrets(self):
        config = self._run("describe-config")
        self.assertEqual(config.returncode, 0)
        body = json.loads(config.stdout)
        self.assertTrue(body["credentials_present"])
        self.assertFalse(body["credentials_exposed"])
        self.assertNotIn("DUMMYSECRETKEY", config.stdout)
        dry = self._run("upload", "--file", str(SCRIPT), "--dry-run")
        self.assertEqual(dry.returncode, 0)
        self.assertNotIn("DUMMYSECRETKEY", dry.stdout + dry.stderr)
        self.assertEqual(json.loads(dry.stdout)["action"], "upload")


if __name__ == "__main__":
    unittest.main()
