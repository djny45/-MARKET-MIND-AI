"""Private-mode preflight must fail closed and never expose values."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import private_mode_check  # noqa: E402

HASH = "scrypt$16384$8$1$c2FsdA$abcdef0123456789abcdef0123456789"


def _env(**overrides):
    base = {
        "MARKET_MIND_USER_AUTH": "true",
        "MARKET_MIND_USERS": json.dumps([
            {"username": "admin", "password_hash": HASH, "role": "admin"},
            {"username": "viewer", "password_hash": HASH, "role": "viewer"},
        ]),
        "FRONTEND_ORIGINS": "http://127.0.0.1:8080",
        "MARKET_MIND_REQUIRE_ORIGIN": "true",
    }
    base.update(overrides)
    return base


class PrivateModeCheckTests(unittest.TestCase):
    def test_valid_private_environment_passes(self):
        report = private_mode_check.check_private_mode(_env())
        self.assertEqual(report["status"], "pass")
        self.assertEqual(len(report["checks"]), 5)
        self.assertFalse(report["values_exposed"])
        self.assertEqual(report["public_ingress"], "disabled")

    def test_auth_disabled_fails(self):
        report = private_mode_check.check_private_mode(_env(MARKET_MIND_USER_AUTH="false"))
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("user_auth_enabled" in item for item in report["findings"]))

    def test_plaintext_password_fails(self):
        users = [{"username": "admin", "password": "cleartext", "password_hash": HASH,
                  "role": "admin"}]
        report = private_mode_check.check_private_mode(
            _env(MARKET_MIND_USERS=json.dumps(users)))
        self.assertFalse(report["values_exposed"])
        self.assertTrue(any("plaintext password" in item for item in report["findings"]))

    def test_wildcard_or_public_origin_fails(self):
        for origin in ("*", "https://example.com", "http://8.8.8.8"):
            with self.subTest(origin=origin):
                report = private_mode_check.check_private_mode(
                    _env(FRONTEND_ORIGINS=origin))
                self.assertEqual(report["status"], "fail")
                self.assertTrue(any("private_origins" in item for item in report["findings"]))

    def test_missing_admin_fails(self):
        users = [{"username": "viewer", "password_hash": HASH, "role": "viewer"}]
        report = private_mode_check.check_private_mode(
            _env(MARKET_MIND_USERS=json.dumps(users)))
        self.assertTrue(any("admin" in item for item in report["findings"]))

    def test_secret_values_are_not_reported(self):
        report = private_mode_check.check_private_mode(_env())
        text = json.dumps(report)
        self.assertNotIn(HASH, text)
        self.assertNotIn("cleartext", text)


if __name__ == "__main__":
    unittest.main()
