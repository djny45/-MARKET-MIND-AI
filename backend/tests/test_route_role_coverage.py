"""Deny-by-default role coverage for every registered API route.

Regression guard for the finding that 160 of 188 routes had a valid-session
check but no role check, letting a ``viewer`` write agent memory, enqueue
research tasks and invoke the supervisor. This test derives expectations from
the live FastAPI route table, so a newly added route cannot silently escape.
"""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_crypto import hash_password
from app.authorization import VIEWER_WRITE_ALLOWLIST, required_role_for_path
from app.main import app
from app.user_auth import CSRF_HEADER

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# These are setup/lifecycle routes that cannot require a role by construction,
# or are explicitly delegated to per-resource ownership checks in the handler.
DELEGATED_PREFIXES = (
    "/api/auth/login",
    "/api/auth/logout",
    "/api/health",
    "/api/ready",
)


def _session_headers(csrf: str) -> dict[str, str]:
    return {"Origin": "http://localhost:5173", CSRF_HEADER: csrf}


class RouteRoleCoverageTests(unittest.TestCase):
    """Every mutating route resolves to a non-viewer minimum role."""

    def test_every_mutating_route_requires_at_least_analyst(self):
        gaps = []
        for route in app.routes:
            methods = getattr(route, "methods", set()) or set()
            path = getattr(route, "path", "")
            if not path.startswith("/api/"):
                continue
            for method in methods & WRITE_METHODS:
                if any(path.startswith(prefix) for prefix in DELEGATED_PREFIXES):
                    continue
                if any(pattern.match(path) for pattern in VIEWER_WRITE_ALLOWLIST):
                    continue  # per-resource ownership check in the handler
                policy = required_role_for_path(path, method)
                if policy is None or policy[0] == "viewer":
                    gaps.append(f"{method} {path}")
        self.assertEqual(gaps, [], f"mutating routes without role gate: {gaps}")

    def test_read_only_routes_stay_viewer_accessible(self):
        # The default must not accidentally lock the terminal out.
        for path in ("/api/markets", "/api/audit/events", "/api/workers",
                     "/api/skills", "/api/daily/status", "/api/terminal/providers"):
            self.assertIsNone(required_role_for_path(path, "GET"), path)

    def test_allowlist_is_narrow(self):
        patterns = [p.pattern for p in VIEWER_WRITE_ALLOWLIST]
        self.assertEqual(len(patterns), 3, patterns)
        self.assertTrue(all(p.startswith("^/api/") for p in patterns))


class ViewerCannotMutateTests(unittest.TestCase):
    """Black-box proof against the real middleware (not just the policy fn)."""

    def setUp(self):
        import json
        import os
        import tempfile

        from app import login_guard

        self.tmp = tempfile.TemporaryDirectory()
        self.users = json.dumps([
            {"username": "admin", "password_hash": hash_password("admin-long-password"), "role": "admin"},
            {"username": "viewer", "password_hash": hash_password("viewer-long-password"), "role": "viewer"},
        ])
        self.env = {
            "MARKET_MIND_USER_AUTH": "true",
            "MARKET_MIND_USERS": self.users,
            "MARKET_MIND_DB": self.tmp.name + "/role.db",
            "MARKET_MIND_REQUIRE_ORIGIN": "false",
        }
        self.env_patch = patch.dict(os.environ, self.env, clear=False)
        self.env_patch.start()
        login_guard.GUARD.reset()
        self.client = TestClient(app)

    def tearDown(self):
        from app import login_guard

        login_guard.GUARD.reset()
        self.env_patch.stop()
        self.tmp.cleanup()

    def _login(self, username: str, password: str) -> str:
        response = self.client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["csrf_token"]

    def test_viewer_cannot_write_agent_memory(self):
        csrf = self._login("viewer", "viewer-long-password")
        response = self.client.post(
            "/api/workers/worker_001/memory",
            json={"memory_type": "observation", "content": {"note": "denied"}},
            headers=_session_headers(csrf),
        )
        self.assertEqual(response.status_code, 403, response.text)
        self.assertIn("insufficient_role", response.json()["detail"])

    def test_viewer_cannot_enqueue_research_task(self):
        csrf = self._login("viewer", "viewer-long-password")
        response = self.client.post(
            "/api/analytical-agents/worker_001/tasks/queue",
            json={"node_type": "research_summary", "brief": "denied", "inputs": {}},
            headers=_session_headers(csrf),
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_viewer_cannot_dispatch_supervisor_or_recover_tasks(self):
        csrf = self._login("viewer", "viewer-long-password")
        for path in ("/api/analytical-agent-supervisor/dispatch",
                     "/api/analytical-agent-tasks/recover"):
            with self.subTest(path=path):
                response = self.client.post(path, json={}, headers=_session_headers(csrf))
                self.assertEqual(response.status_code, 403, response.text)

    def test_viewer_can_still_mutate_own_workspace_and_watchlist(self):
        csrf = self._login("viewer", "viewer-long-password")
        created = self.client.post(
            "/api/workspaces",
            json={"title": "viewer-ws", "nodes": [], "edges": []},
            headers=_session_headers(csrf),
        )
        self.assertIn(created.status_code, (200, 201), created.text)
        watched = self.client.post(
            "/api/watchlist", json={"symbol": "AAPL"}, headers=_session_headers(csrf)
        )
        self.assertIn(watched.status_code, (200, 201), watched.text)

    def test_admin_still_can_do_everything_viewer_cannot(self):
        csrf = self._login("admin", "admin-long-password")
        response = self.client.post(
            "/api/workers/worker_001/memory",
            json={"memory_type": "observation", "content": {"note": "allowed"}},
            headers=_session_headers(csrf),
        )
        self.assertIn(response.status_code, (200, 201), response.text)


if __name__ == "__main__":
    unittest.main()
