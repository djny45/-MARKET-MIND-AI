import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_crypto import hash_password
from app.main import app
from app.auth_api import _allowed_origins


class AuthenticationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.password = "test-owner-password-with-sufficient-length"
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_AUTH_REQUIRED": "true",
            "MARKET_MIND_OWNER_PASSWORD_HASH": hash_password(self.password),
            "MARKET_MIND_AUTH_DB": os.path.join(self.temp.name, "auth.sqlite3"),
            "MARKET_MIND_DB": os.path.join(self.temp.name, "market.sqlite3"),
            "MARKET_MIND_COOKIE_SECURE": "false",
            "FRONTEND_ORIGINS": "http://testserver",
        })
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def test_public_health_and_default_deny_for_workspace_routes(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        response = self.client.get("/api/watchlist")
        self.assertEqual(response.status_code, 401)

    def test_api_schema_and_interactive_docs_are_disabled(self):
        for path in ("/docs", "/redoc", "/openapi.json"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_allowed_origins_reject_non_origin_urls(self):
        invalid_origins = (
            "*",
            "https://example.com/path",
            "https://user:password@example.com",
            "https://example.com?next=/",
            "https://example.com#fragment",
            "ftp://example.com",
            "https://example.com, *",
        )
        for configured in invalid_origins:
            with self.subTest(configured=configured):
                with patch.dict(os.environ, {"FRONTEND_ORIGINS": configured}):
                    with self.assertRaises(RuntimeError):
                        _allowed_origins()

    def test_allowed_origins_normalize_scheme_host_and_default_port(self):
        with patch.dict(
            os.environ,
            {"FRONTEND_ORIGINS": "HTTPS://Example.COM:443/,http://LocalHost:80"},
        ):
            self.assertEqual(
                _allowed_origins(),
                {"https://example.com", "http://localhost"},
            )

    def test_login_session_csrf_and_logout_lifecycle(self):
        origin = {"Origin": "http://testserver"}
        denied = self.client.post("/api/auth/login", json={"password": self.password})
        self.assertEqual(denied.status_code, 403)

        login = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["authenticated"])
        self.assertIn("market_mind_session", self.client.cookies)
        self.assertIn("market_mind_csrf", self.client.cookies)

        session = self.client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["user"], "owner")

        blocked = self.client.post("/api/watchlist", json={"symbol": "BTCUSD"}, headers=origin)
        self.assertEqual(blocked.status_code, 403)

        csrf = self.client.cookies.get("market_mind_csrf")
        allowed = self.client.post(
            "/api/watchlist",
            json={"symbol": "BTCUSD"},
            headers={**origin, "x-csrf-token": csrf},
        )
        self.assertEqual(allowed.status_code, 200)

        logout = self.client.post(
            "/api/auth/logout",
            headers={**origin, "x-csrf-token": csrf},
        )
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/api/watchlist").status_code, 401)

    def test_invalid_password_does_not_create_session(self):
        response = self.client.post(
            "/api/auth/login",
            json={"password": "incorrect"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("market_mind_session", self.client.cookies)

    def test_login_rotation_revokes_previous_session(self):
        from app.auth_crypto import hash_session_token
        from app.auth_session_store import get_session

        origin = {"Origin": "http://testserver"}
        first = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(first.status_code, 200)
        old_token = self.client.cookies.get("market_mind_session")
        old_hash = hash_session_token(old_token)

        second = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(self.client.cookies.get("market_mind_session"), old_token)
        old_session = get_session(
            os.path.join(self.temp.name, "auth.sqlite3"),
            old_hash,
            now=int(time.time()),
            idle_ttl_seconds=1800,
        )
        self.assertIsNone(old_session)

    def test_login_returns_service_unavailable_when_session_store_fails(self):
        from unittest.mock import patch

        with patch("app.auth_api._ensure_store", side_effect=sqlite3.OperationalError("db unavailable")):
            response = self.client.post(
                "/api/auth/login",
                json={"password": self.password},
                headers={"Origin": "http://testserver"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Authentication storage unavailable")

    def test_missing_owner_secret_fails_closed(self):
        with patch.dict(os.environ, {"MARKET_MIND_OWNER_PASSWORD_HASH": ""}):
            response = self.client.get("/api/watchlist")
        self.assertEqual(response.status_code, 503)


    def test_authenticated_mutation_rejects_bad_csrf_and_untrusted_origin(self):
        origin = {"Origin": "http://testserver"}
        login = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(login.status_code, 200)
        csrf = self.client.cookies.get("market_mind_csrf")

        bad_csrf = self.client.post(
            "/api/watchlist",
            json={"symbol": "BTCUSD"},
            headers={**origin, "x-csrf-token": "not-the-csrf-token"},
        )
        self.assertEqual(bad_csrf.status_code, 403)
        self.assertEqual(bad_csrf.json()["detail"], "CSRF validation failed")

        bad_origin = self.client.post(
            "/api/watchlist",
            json={"symbol": "BTCUSD"},
            headers={"Origin": "https://attacker.invalid", "x-csrf-token": csrf},
        )
        self.assertEqual(bad_origin.status_code, 403)
        self.assertEqual(bad_origin.json()["detail"], "Origin not allowed")

    def test_login_throttle_blocks_repeated_failures(self):
        from app.auth_api import _LOGIN_ATTEMPTS, _RATE_LOCK, _clear_login_attempts

        client_key = "testclient"
        with _RATE_LOCK:
            _LOGIN_ATTEMPTS.pop(client_key, None)
        try:
            with patch("app.auth_api._RATE_MAX_ATTEMPTS", 1):
                first = self.client.post(
                    "/api/auth/login",
                    json={"password": "incorrect"},
                    headers={"Origin": "http://testserver"},
                )
                second = self.client.post(
                    "/api/auth/login",
                    json={"password": "incorrect"},
                    headers={"Origin": "http://testserver"},
                )
            self.assertEqual(first.status_code, 401)
            self.assertEqual(second.status_code, 429)
        finally:
            _clear_login_attempts(client_key)

    def test_authenticated_request_fails_closed_when_session_store_is_unavailable(self):
        origin = {"Origin": "http://testserver"}
        login = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(login.status_code, 200)

        with patch(
            "app.auth_api._ensure_store",
            side_effect=sqlite3.OperationalError("db unavailable"),
        ):
            response = self.client.get("/api/watchlist")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Authentication storage unavailable")


    def test_login_rotation_fails_closed_when_previous_session_cannot_be_revoked(self):
        origin = {"Origin": "http://testserver"}
        first = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(first.status_code, 200)
        original_token = self.client.cookies.get("market_mind_session")

        with patch(
            "app.auth_api.revoke_session",
            side_effect=sqlite3.OperationalError("db unavailable"),
        ):
            second = self.client.post(
                "/api/auth/login", json={"password": self.password}, headers=origin
            )

        self.assertEqual(second.status_code, 503)
        self.assertEqual(
            second.json()["detail"], "Authentication storage unavailable"
        )
        self.assertEqual(self.client.cookies.get("market_mind_session"), original_token)


    def test_logout_fails_closed_when_session_revocation_storage_fails(self):
        origin = {"Origin": "http://testserver"}
        login = self.client.post(
            "/api/auth/login", json={"password": self.password}, headers=origin
        )
        self.assertEqual(login.status_code, 200)
        csrf = self.client.cookies.get("market_mind_csrf")

        with patch(
            "app.auth_api.revoke_session",
            side_effect=sqlite3.OperationalError("db unavailable"),
        ):
            logout = self.client.post(
                "/api/auth/logout",
                headers={**origin, "x-csrf-token": csrf},
            )

        self.assertEqual(logout.status_code, 503)
        self.assertEqual(
            logout.json()["detail"], "Authentication storage unavailable"
        )


    def test_login_throttle_bounds_distinct_client_buckets(self):
        from app.auth_api import (
            _LOGIN_ATTEMPTS,
            _RATE_LOCK,
            _RATE_OVERFLOW_KEY,
            _clear_login_attempts,
            _login_rate_limited,
        )

        keys = ("bucket-test-a", "bucket-test-b", "bucket-test-c", "bucket-test-d")
        with _RATE_LOCK:
            for key in (*keys, _RATE_OVERFLOW_KEY):
                _LOGIN_ATTEMPTS.pop(key, None)

        try:
            with patch("app.auth_api._RATE_MAX_KEYS", 2), patch(
                "app.auth_api._RATE_MAX_ATTEMPTS", 10
            ):
                self.assertFalse(_login_rate_limited(keys[0], now=100))
                self.assertFalse(_login_rate_limited(keys[1], now=100))
                self.assertFalse(_login_rate_limited(keys[2], now=100))
                self.assertFalse(_login_rate_limited(keys[3], now=100))

            with _RATE_LOCK:
                self.assertIn(_RATE_OVERFLOW_KEY, _LOGIN_ATTEMPTS)
                self.assertNotIn(keys[2], _LOGIN_ATTEMPTS)
                self.assertNotIn(keys[3], _LOGIN_ATTEMPTS)
                self.assertLessEqual(len(_LOGIN_ATTEMPTS), 3)
        finally:
            for key in (*keys, _RATE_OVERFLOW_KEY):
                _clear_login_attempts(key)



    def test_login_throttle_prunes_expired_buckets_before_overflow(self):
        from app.auth_api import (
            _LOGIN_ATTEMPTS,
            _RATE_LOCK,
            _RATE_OVERFLOW_KEY,
            _clear_login_attempts,
            _login_rate_limited,
        )

        keys = ("bucket-expired-a", "bucket-expired-b", "bucket-expired-c")
        with _RATE_LOCK:
            for key in (*keys, _RATE_OVERFLOW_KEY):
                _LOGIN_ATTEMPTS.pop(key, None)

        try:
            with patch("app.auth_api._RATE_MAX_KEYS", 2), patch(
                "app.auth_api._RATE_WINDOW_SECONDS", 60
            ):
                self.assertFalse(_login_rate_limited(keys[0], now=10))
                self.assertFalse(_login_rate_limited(keys[1], now=10))
                # Both existing buckets have expired by this request. The new
                # identity should get its own bucket, not the shared overflow.
                self.assertFalse(_login_rate_limited(keys[2], now=71))

            with _RATE_LOCK:
                self.assertIn(keys[2], _LOGIN_ATTEMPTS)
                self.assertNotIn(keys[0], _LOGIN_ATTEMPTS)
                self.assertNotIn(keys[1], _LOGIN_ATTEMPTS)
                self.assertNotIn(_RATE_OVERFLOW_KEY, _LOGIN_ATTEMPTS)
        finally:
            for key in (*keys, _RATE_OVERFLOW_KEY):
                _clear_login_attempts(key)


    def test_session_and_csrf_cookie_security_attributes(self):
        with patch.dict(os.environ, {"MARKET_MIND_COOKIE_SECURE": "true"}):
            response = self.client.post(
                "/api/auth/login",
                json={"password": self.password},
                headers={"Origin": "http://testserver"},
            )
        self.assertEqual(response.status_code, 200)
        set_cookie_headers = response.headers.get_list("set-cookie")
        session_cookie = next(
            value for value in set_cookie_headers
            if value.startswith("market_mind_session=")
        )
        csrf_cookie = next(
            value for value in set_cookie_headers
            if value.startswith("market_mind_csrf=")
        )
        self.assertIn("httponly", session_cookie.lower())
        self.assertIn("secure", session_cookie.lower())
        self.assertIn("samesite=strict", session_cookie.lower())
        self.assertNotIn("httponly", csrf_cookie.lower())
        self.assertIn("secure", csrf_cookie.lower())
        self.assertIn("samesite=strict", csrf_cookie.lower())


if __name__ == "__main__":
    unittest.main()
