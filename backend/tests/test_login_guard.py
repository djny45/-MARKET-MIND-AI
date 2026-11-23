"""Tests for failed-login throttling and lockout."""
import unittest
from unittest.mock import patch

from app.login_guard import LoginGuard


class LoginGuardTests(unittest.TestCase):
    def test_below_threshold_allows(self):
        guard = LoginGuard()
        for _ in range(4):
            guard.record_failure("alice", "10.0.0.1")
        self.assertTrue(guard.check("alice", "10.0.0.1")[0])

    def test_lockout_at_threshold_with_backoff(self):
        now = [0.0]
        guard = LoginGuard(clock=lambda: now[0])
        for _ in range(5):
            guard.record_failure("alice", "10.0.0.1")
        allowed, retry = guard.check("alice", "10.0.0.1")
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)
        now[0] += retry + 1
        self.assertTrue(guard.check("alice", "10.0.0.1")[0])

    def test_keys_are_per_account_and_per_client(self):
        guard = LoginGuard()
        for _ in range(5):
            guard.record_failure("alice", "10.0.0.1")
        self.assertTrue(guard.check("alice", "10.0.0.2")[0])
        self.assertTrue(guard.check("bob", "10.0.0.1")[0])

    def test_success_clears_failures(self):
        guard = LoginGuard()
        guard.record_failure("alice", "10.0.0.1")
        guard.record_failure("alice", "10.0.0.1")
        guard.record_success("alice", "10.0.0.1")
        self.assertTrue(guard.check("alice", "10.0.0.1")[0])

    def test_settings_from_env(self):
        with patch.dict("os.environ", {
            "MARKET_MIND_LOGIN_MAX_FAILURES": "3",
            "MARKET_MIND_LOGIN_WINDOW_SECONDS": "60",
            "MARKET_MIND_LOGIN_LOCKOUT_SECONDS": "10",
        }):
            from app.login_guard import settings
            self.assertEqual(settings(), {"max_failures": 3, "window_seconds": 60, "lockout_seconds": 10})


if __name__ == "__main__":
    unittest.main()
