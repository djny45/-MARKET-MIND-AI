import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_crypto import hash_password
from app.main import app


class UserAuthApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "auth.db"
        users = json.dumps([
            {"username": "admin", "password_hash": hash_password("admin-long-password"), "role": "admin"},
            {"username": "viewer", "password_hash": hash_password("viewer-long-password"), "role": "viewer"},
        ])
        self.env = {
            "MARKET_MIND_USER_AUTH": "true",
            "MARKET_MIND_USERS": users,
            "MARKET_MIND_DB": str(self.db),
        }
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_login_me_and_logout(self):
        with patch.dict(os.environ, self.env, clear=False):
            response = self.client.post(
                "/api/auth/login", json={"username": "admin", "password": "admin-long-password"}
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["role"], "admin")
            csrf = body["csrf_token"]
            self.assertIn("mm_session", response.cookies)

            me = self.client.get("/api/auth/me")
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["user"]["username"], "admin")

            logout = self.client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
            self.assertEqual(logout.status_code, 200)
            self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_invalid_login_is_rejected(self):
        with patch.dict(os.environ, self.env, clear=False):
            response = self.client.post(
                "/api/auth/login", json={"username": "admin", "password": "wrong"}
            )
            self.assertEqual(response.status_code, 401)

    def test_viewer_cannot_use_operator_endpoint(self):
        with patch.dict(os.environ, self.env, clear=False):
            login = self.client.post(
                "/api/auth/login", json={"username": "viewer", "password": "viewer-long-password"}
            )
            self.assertEqual(login.status_code, 200)
            csrf = login.json()["csrf_token"]
            attempt = self.client.post(
                "/api/workers/worker_001/memory/memory_001/review",
                headers={"X-CSRF-Token": csrf},
                json={"decision": "approved", "reviewer": "viewer"},
            )
            self.assertEqual(attempt.status_code, 403)

    def test_user_auth_disabled_by_default(self):
        with patch.dict(os.environ, {"MARKET_MIND_USER_AUTH": "false"}, clear=False):
            self.assertEqual(self.client.get("/api/auth/me").json()["enabled"], False)
            self.assertEqual(self.client.post("/api/auth/login", json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
