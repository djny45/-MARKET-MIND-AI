"""Failed-login throttling and timing equalisation on the credential endpoint.

Before this, `/api/auth/login` accepted unlimited attempts (`RateLimitMiddleware`
is disabled unless an operator configures it), and an unknown username answered
in ~0 ms while a real account cost ~32 ms of scrypt work — a free username
oracle and a free guessing oracle.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import auth_crypto, login_guard, user_auth
from app.login_guard import LoginGuard
from app.main import app


class LoginGuardTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000.0
        self.guard = LoginGuard(clock=lambda: self.now)

    def test_allows_attempts_below_the_threshold(self):
        for _ in range(4):
            self.guard.record_failure("alice", "1.2.3.4")
        allowed, retry_after = self.guard.check("alice", "1.2.3.4")
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)

    def test_locks_out_after_the_threshold_and_reports_a_wait(self):
        for _ in range(5):
            result = self.guard.record_failure("alice", "1.2.3.4")
        self.assertGreater(result["locked_for"], 0)
        allowed, retry_after = self.guard.check("alice", "1.2.3.4")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    def test_lockout_doubles_on_repeat_offences_and_is_capped(self):
        first = None
        for round_index in range(3):
            for _ in range(5):
                result = self.guard.record_failure("alice", "1.2.3.4")
            if first is None:
                first = result["locked_for"]
            self.now += result["locked_for"] + 1
        self.assertGreater(result["locked_for"], first)
        self.assertLessEqual(result["locked_for"], login_guard.settings()["window_seconds"])

    def test_lockout_expires(self):
        for _ in range(5):
            self.guard.record_failure("alice", "1.2.3.4")
        self.assertFalse(self.guard.check("alice", "1.2.3.4")[0])
        self.now += login_guard.settings()["window_seconds"] + 1
        self.assertTrue(self.guard.check("alice", "1.2.3.4")[0])

    def test_successful_login_clears_the_counter(self):
        for _ in range(4):
            self.guard.record_failure("alice", "1.2.3.4")
        self.guard.record_success("alice", "1.2.3.4")
        for _ in range(4):
            self.guard.record_failure("alice", "1.2.3.4")
        self.assertTrue(self.guard.check("alice", "1.2.3.4")[0])

    def test_failures_age_out_of_the_window(self):
        for _ in range(4):
            self.guard.record_failure("alice", "1.2.3.4")
        self.now += login_guard.settings()["window_seconds"] + 1
        result = self.guard.record_failure("alice", "1.2.3.4")
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["locked_for"], 0)

    def test_other_accounts_and_addresses_are_not_affected(self):
        for _ in range(5):
            self.guard.record_failure("alice", "1.2.3.4")
        self.assertTrue(self.guard.check("bob", "1.2.3.4")[0])
        self.assertTrue(self.guard.check("alice", "5.6.7.8")[0])

    def test_tracked_keys_are_bounded(self):
        for index in range(self.guard.max_tracked_keys + 500):
            self.guard.record_failure(f"user{index}", "1.2.3.4")
        self.assertLessEqual(self.guard.tracked_keys(), self.guard.max_tracked_keys)


class LoginTimingTests(unittest.TestCase):
    def test_unknown_account_costs_the_same_scrypt_work_as_a_real_one(self):
        password_hash = auth_crypto.hash_password("correct-horse-battery-staple")
        env = {"MARKET_MIND_USERS": json.dumps(
            [{"username": "alice", "password_hash": password_hash, "role": "admin"}])}

        def measure(username: str) -> float:
            start = time.perf_counter()
            self.assertIsNone(user_auth.authenticate(username, "wrong-password", env))
            return (time.perf_counter() - start) * 1000

        known = min(measure("alice") for _ in range(3))
        unknown = min(measure("ghost") for _ in range(3))
        # scrypt at N=2**14 costs tens of milliseconds; a miss must not skip it.
        self.assertGreater(unknown, 5.0, "unknown account returned without hashing")
        self.assertGreater(unknown, known / 4, "timing reveals whether the account exists")


class LoginEndpointTests(unittest.TestCase):
    def setUp(self):
        login_guard.GUARD.reset()
        self._dir = tempfile.TemporaryDirectory()
        self.env = {
            "MARKET_MIND_USER_AUTH": "1",
            "MARKET_MIND_DB": os.path.join(self._dir.name, "auth.db"),
            "MARKET_MIND_USERS": json.dumps([{
                "username": "alice",
                "password_hash": auth_crypto.hash_password("correct-horse-battery-staple"),
                "role": "admin",
            }]),
            "MARKET_MIND_LOGIN_MAX_FAILURES": "3",
        }

    def tearDown(self):
        login_guard.GUARD.reset()
        self._dir.cleanup()

    def _client(self) -> TestClient:
        client = TestClient(app)
        client.headers.update({"Origin": "http://localhost:5173"})
        return client

    def test_repeated_failures_return_429_with_retry_after(self):
        with patch.dict(os.environ, self.env, clear=False):
            client = self._client()
            statuses = [
                client.post("/api/auth/login",
                            json={"username": "alice", "password": "wrong"}).status_code
                for _ in range(3)
            ]
            blocked = client.post("/api/auth/login",
                                  json={"username": "alice", "password": "wrong"})
        self.assertEqual(statuses, [401, 401, 401])
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers["Retry-After"]), 0)

    def test_unknown_usernames_are_throttled_the_same_way(self):
        with patch.dict(os.environ, self.env, clear=False):
            client = self._client()
            for _ in range(3):
                client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
            blocked = client.post("/api/auth/login",
                                  json={"username": "ghost", "password": "x"})
        self.assertEqual(blocked.status_code, 429)

    def test_successful_login_still_works_after_failures(self):
        with patch.dict(os.environ, self.env, clear=False):
            client = self._client()
            for _ in range(2):
                client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
            ok = client.post("/api/auth/login", json={
                "username": "alice", "password": "correct-horse-battery-staple"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["role"], "admin")
        self.assertTrue(login_guard.check_login("alice", "testclient")[0])


if __name__ == "__main__":
    unittest.main()
