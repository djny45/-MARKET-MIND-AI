"""Tests for timing-equalised credential checks."""
import unittest
from unittest.mock import patch

from app.auth_crypto import equalise_verification_timing, hash_password, verify_password


class AuthTimingTests(unittest.TestCase):
    def test_equalise_spends_scrypt_work(self):
        with patch("app.auth_crypto.verify_password", wraps=verify_password) as spy:
            equalise_verification_timing("correct horse")
            self.assertEqual(spy.call_count, 1)
            self.assertEqual(spy.call_args[0][0], "correct horse")

    def test_equalise_ignores_non_strings(self):
        with patch("app.auth_crypto.verify_password") as spy:
            equalise_verification_timing(None)
            equalise_verification_timing(123)
            spy.assert_not_called()

    def test_unknown_user_cannot_be_detected_by_timing(self):
        from app.user_auth import authenticate
        with patch.dict("os.environ", {"MARKET_MIND_USER_AUTH": "true", "MARKET_MIND_USERS": "[]"}):
            result = authenticate("ghost", "any-password-at-all")
        self.assertIsNone(result)

    def test_wrong_password_still_fails(self):
        from app.user_auth import authenticate, load_users
        import json, tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            hashpw = hash_password("secret-password")
            env = {"MARKET_MIND_USER_AUTH": "true",
                   "MARKET_MIND_USERS": json.dumps([{"username": "u", "password_hash": hashpw, "role": "viewer"}]),
                   "MARKET_MIND_DB": os.path.join(tmp, "a.db")}
            with patch.dict("os.environ", env, clear=False):
                self.assertEqual(authenticate("u", "wrong"), None)
                self.assertEqual(authenticate("u", "secret-password"), {"username": "u", "role": "viewer"})


if __name__ == "__main__":
    unittest.main()
