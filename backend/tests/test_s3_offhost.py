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

    def test_invalid_bucket_and_remote_http_endpoint_fail_closed(self):
        for name, value, expected in (
            ("MARKET_MIND_S3_BUCKET", "Bad_Bucket", "invalid_bucket_name"),
            ("MARKET_MIND_S3_ENDPOINT", "http://s3.remote.invalid", "https_required_outside_loopback"),
            ("MARKET_MIND_S3_PREFIX", "a/../b", "unsafe_prefix"),
        ):
            env = dict(self.env, **{name: value})
            result = self._run("describe-config", env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stderr)
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_validate_config_fails_closed_with_no_credentials(self):
        env = {k: v for k, v in self.env.items() if not k.startswith("MARKET_MIND_S3_")}
        result = self._run("validate-config", env=env)
        self.assertNotEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "failed")
        self.assertIn("missing_required_variables",
                      [item["issue"] for item in body["findings"]])
        self.assertEqual(len(body["missing_variables"]), 5)
        self.assertFalse(body["values_exposed"])

    def test_validate_config_reports_findings_without_values(self):
        result = self._run("validate-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "ok")
        env = dict(self.env, MARKET_MIND_S3_BUCKET="Bad_Bucket")
        failed = self._run("validate-config", env=env)
        self.assertNotEqual(failed.returncode, 0)
        body = json.loads(failed.stdout)
        self.assertEqual(body["status"], "failed")
        self.assertNotIn("Bad_Bucket", failed.stdout + failed.stderr)

    def test_endpoint_base_path_is_rejected(self):
        env = dict(self.env, MARKET_MIND_S3_ENDPOINT="https://s3.example.invalid/base")
        result = self._run("describe-config", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("base path", result.stderr)
        self.assertNotIn("/base", result.stdout)

    def test_unsafe_object_key_is_rejected(self):
        source = ROOT / "README.md"
        for key in ("../escape.db", "/absolute.db", "a/b?x=1", "a b.db"):
            result = self._run("upload", "--file", str(source), "--key", key)
            self.assertNotEqual(result.returncode, 0, key)
            self.assertIn("unsafe object key", result.stderr)

    def test_endpoint_userinfo_is_rejected_and_never_printed(self):
        env = dict(self.env, MARKET_MIND_S3_ENDPOINT="https://user:topsecret@s3.example.invalid")
        result = self._run("describe-config", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("topsecret", result.stdout + result.stderr)
        self.assertIn("user information", result.stderr)

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
