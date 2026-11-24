"""Regressions for confirmed security defects in auth, throttling and audit."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import distributed_rate_limit, login_guard, rate_limit
from app.audit_events import audit_log
from app.auth_crypto import generate_session_token, hash_password, hash_session_token
from app.auth_session_store import initialize_auth_store, purge_expired_sessions
from app.distributed_rate_limit import _LocalWindow
from app.main import app
from app.rate_limit import RateLimitMiddleware
from app.user_session_middleware import _origin_allowed


class _MiddlewareCase(unittest.IsolatedAsyncioTestCase):
    async def _call(self, middleware, headers=(), path="/api/private"):
        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        seen = {"status": None}

        async def send(message):
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": list(headers), "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
        }
        middleware.app = downstream
        await middleware(scope, receive, send)
        return seen["status"]


class SecurityRegressions(_MiddlewareCase):
    def test_malformed_origin_is_ignored_not_a_server_error(self):
        scope = {"headers": [(b"origin", b"http://[")]}
        with patch.dict(os.environ, {"FRONTEND_ORIGINS": "https://app.example"}):
            self.assertFalse(_origin_allowed(scope))
            scope["headers"].append((b"origin", b"https://app.example"))
            self.assertTrue(_origin_allowed(scope))

    async def test_rate_limit_denials_are_audited(self):
        audit_log.clear()
        middleware = RateLimitMiddleware(None)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}):
            self.assertEqual(await self._call(middleware), 204)
            self.assertEqual(await self._call(middleware), 429)
        events = audit_log.recent(event_type="rate_limit")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "throttled")
        audit_log.clear()

    async def test_key_flood_does_not_clear_throttled_clients(self):
        with patch.object(rate_limit, "MAX_TRACKED_CLIENTS", 3), \
             patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}):
            middleware = RateLimitMiddleware(None)
            self.assertEqual(await self._call(middleware, [(b"x-forwarded-for", b"10.0.0.1")]), 204)
            self.assertEqual(await self._call(middleware, [(b"x-forwarded-for", b"10.0.0.1")]), 429)
            for index in range(10):
                await self._call(middleware, [(b"x-forwarded-for", f"10.1.0.{index}".encode())])
            self.assertEqual(await self._call(middleware, [(b"x-forwarded-for", b"10.0.0.1")]), 429)

    def test_local_window_evicts_one_key_not_all(self):
        with patch.object(distributed_rate_limit, "MAX_TRACKED_CLIENTS", 3):
            limiter = _LocalWindow()
            self.assertTrue(limiter.check("victim", 1, 100.0).allowed)
            self.assertFalse(limiter.check("victim", 1, 100.1).allowed)
            for index in range(10):
                limiter.check(f"noise-{index}", 1, 100.2)
            self.assertFalse(limiter.check("victim", 1, 100.3).allowed)

    def test_active_login_lockout_survives_key_flood(self):
        env = {
            "MARKET_MIND_LOGIN_MAX_FAILURES": "2",
            "MARKET_MIND_LOGIN_WINDOW_SECONDS": "900",
            "MARKET_MIND_LOGIN_LOCKOUT_SECONDS": "300",
        }
        guard = login_guard.LoginGuard(clock=lambda: 1000.0, max_tracked_keys=3)
        with patch.dict(os.environ, env):
            guard.record_failure("victim", "10.0.0.1")
            guard.record_failure("victim", "10.0.0.1")
            self.assertFalse(guard.check("victim", "10.0.0.1")[0])
            for index in range(6):
                guard.record_failure(f"noise-{index}", "10.0.0.9")
            allowed, retry = guard.check("victim", "10.0.0.1")
            self.assertFalse(allowed)
            self.assertGreater(retry, 0)

    def test_failed_login_audit_records_attempted_username(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "auth.db"
        users = json.dumps([
            {"username": "alice", "password_hash": hash_password("alice-long-password"),
             "role": "viewer"},
        ])
        env = {
            "MARKET_MIND_USER_AUTH": "true", "MARKET_MIND_USERS": users,
            "MARKET_MIND_DB": str(db), "ENV_VALIDATION_STRICT": "",
        }
        login_guard.GUARD.reset()
        audit_log.clear()
        with patch.dict(os.environ, env, clear=False):
            response = TestClient(app).post(
                "/api/auth/login", json={"username": "alice", "password": "wrong-password"}
            )
        self.assertEqual(response.status_code, 401)
        events = [event for event in audit_log.recent(event_type="authentication")
                  if event["outcome"] == "denied"]
        self.assertTrue(events)
        self.assertEqual(events[-1]["metadata"].get("attempted_username"), "alice")
        self.assertEqual(events[-1]["actor"], "alice")
        login_guard.GUARD.reset()
        audit_log.clear()

    def test_purge_expired_sessions_removes_identity_rows(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "auth.db"
        initialize_auth_store(db)
        digest = hash_session_token(generate_session_token())
        with sqlite3.connect(db) as connection:
            connection.execute(
                "INSERT INTO auth_sessions VALUES (?,?,?,?,?,?,?)",
                (digest, "c" * 64, 100, 100, 110, 110, None),
            )
            connection.execute(
                "CREATE TABLE auth_session_identities "
                "(session_token_hash TEXT PRIMARY KEY, username TEXT, role TEXT)"
            )
            connection.execute(
                "INSERT INTO auth_session_identities VALUES (?,?,?)", (digest, "alice", "viewer")
            )
        removed = purge_expired_sessions(db, now=200)
        self.assertEqual(removed, 1)
        with sqlite3.connect(db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM auth_sessions").fetchone()[0], 0)
            self.assertEqual(
                connection.execute("SELECT count(*) FROM auth_session_identities").fetchone()[0], 0
            )


if __name__ == "__main__":
    unittest.main()
