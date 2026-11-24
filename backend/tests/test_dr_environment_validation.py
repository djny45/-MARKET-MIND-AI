"""Deployment preflight for DR variables must fail closed and never echo values."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import dr_common  # noqa: E402

SECRET = "super-secret-hook-value"


class DrEnvironmentValidationTests(unittest.TestCase):
    def test_valid_environment(self):
        result = dr_common.validate_dr_environment({
            "MARKET_MIND_BACKUP_RETENTION_DAYS": "30",
            "MARKET_MIND_BACKUP_KEEP": "5",
            "MARKET_MIND_DR_TIMEOUT_SECONDS": "300",
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "https://ops.example.invalid/hook",
            "MARKET_MIND_S3_ENDPOINT": "http://127.0.0.1:5000",
            "MARKET_MIND_BACKUP_UPLOAD_CMD": "python hook.py {backup} {sha256}",
        })
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["findings"], [])
        self.assertFalse(result["values_exposed"])

    def test_invalid_values_report_variable_names_only(self):
        env = {
            "MARKET_MIND_BACKUP_RETENTION_DAYS": "nonsense",
            "MARKET_MIND_BACKUP_KEEP": "-2",
            "MARKET_MIND_DR_TIMEOUT_SECONDS": "0",
            "MARKET_MIND_BACKUP_MIN_FREE_MB": "-1",
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "ftp://ops.example.invalid/hook",
            "MARKET_MIND_S3_ENDPOINT": "http://s3.example.invalid",
            "MARKET_MIND_BACKUP_UPLOAD_CMD": f"python hook.py --password={SECRET}",
        }
        result = dr_common.validate_dr_environment(env)
        self.assertEqual(result["status"], "failed")
        variables = {finding["variable"] for finding in result["findings"]}
        self.assertIn("MARKET_MIND_BACKUP_RETENTION_DAYS", variables)
        self.assertIn("MARKET_MIND_INCIDENT_WEBHOOK_URL", variables)
        self.assertIn("MARKET_MIND_S3_ENDPOINT", variables)
        self.assertIn("MARKET_MIND_BACKUP_MIN_FREE_MB", variables)
        self.assertIn("MARKET_MIND_BACKUP_UPLOAD_CMD", variables)
        text = json.dumps(result)
        self.assertNotIn(SECRET, text)
        self.assertNotIn("ops.example.invalid", text)

    def test_empty_environment_is_valid(self):
        self.assertEqual(dr_common.validate_dr_environment({})["status"], "ok")


if __name__ == "__main__":
    unittest.main()
