import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_crypto import hash_password
from app.main import app


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
            now=2_000_000_000,
            idle_ttl_seconds=1800,
        )
        self.assertIsNone(old_session)

    def test_missing_owner_secret_fails_closed(self):
        with patch.dict(os.environ, {"MARKET_MIND_OWNER_PASSWORD_HASH": ""}):
            response = self.client.get("/api/watchlist")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
