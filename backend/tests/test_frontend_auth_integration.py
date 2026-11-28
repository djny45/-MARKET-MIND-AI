"""The documented dual-auth deployment must be usable by the shipped browser UI."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import login_guard
from app.auth_crypto import hash_password
from app.main import app


class DualAuthIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        users = json.dumps([
            {"username": "viewer", "password_hash": hash_password("viewer-long-password"),
             "role": "viewer"},
        ])
        self.env = {
            "API_AUTH_REQUIRED": "true",
            "API_AUTH_TOKEN": "deployment-bearer-token-of-sufficient-length",
            "MARKET_MIND_USER_AUTH": "true",
            "MARKET_MIND_USERS": users,
            "MARKET_MIND_DB": str(Path(self.temp.name) / "auth.db"),
            "ENV_VALIDATION_STRICT": "",
        }
        login_guard.GUARD.reset()

    def tearDown(self):
        login_guard.GUARD.reset()


    def test_bearer_only_sensitive_ops_status_is_denied(self):
        # Bearer authentication is service-level viewer access. It must not
        # satisfy the operator role required by /api/ops/status.
        env = dict(self.env, MARKET_MIND_USER_AUTH="false")
        client = TestClient(app)
        with patch.dict(os.environ, env, clear=False):
            response = client.get(
                "/api/ops/status",
                headers={"Authorization": f"Bearer {env['API_AUTH_TOKEN']}"},
            )
        self.assertEqual(response.status_code, 403, response.text)

    def test_session_routes_bypass_bearer_but_other_routes_do_not(self):
        client = TestClient(app)
        with patch.dict(os.environ, self.env, clear=False):
            wrong = client.post("/api/auth/login", json={
                "username": "viewer", "password": "definitely-wrong",
            })
            self.assertEqual(wrong.status_code, 401)
            self.assertEqual(wrong.json()["detail"], "Invalid credentials")

            login = client.post("/api/auth/login", json={
                "username": "viewer", "password": "viewer-long-password",
            })
            self.assertEqual(login.status_code, 200, login.text)
            csrf = login.json()["csrf_token"]

            denied = client.post("/api/watchlist", json={"symbol": "AAPL"})
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json()["detail"], "Valid CSRF token required.")

            created = client.post(
                "/api/watchlist", headers={"X-CSRF-Token": csrf},
                json={"symbol": "AAPL"},
            )
            self.assertIn(created.status_code, (200, 201, 204), created.text)

            # With sessions enabled, ordinary routes work with the session
            # cookie alone (the browser cannot hold the bearer secret).
            self.assertEqual(client.get("/api/workers").status_code, 200)

        # Bearer-only mode still fails closed without the deployment token.
        with patch.dict(os.environ, {**self.env, "MARKET_MIND_USER_AUTH": "false"}):
            bearer_only = TestClient(app)
            self.assertEqual(bearer_only.get("/api/workers").status_code, 401)

            # A deployment-wide bearer authenticates the service client, not
            # an operator. The central sensitive-route policy must therefore
            # deny access to operational details in bearer-only mode.
            operator_data = bearer_only.get(
                "/api/ops/status",
                headers={"Authorization": f"Bearer {self.env['API_AUTH_TOKEN']}"},
            )
            self.assertEqual(operator_data.status_code, 403, operator_data.text)


if __name__ == "__main__":
    unittest.main()
