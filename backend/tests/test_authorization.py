import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_crypto import hash_password
from app.authorization import (
    ResourceRef,
    authorize,
    ownership_registry,
    required_role_for_path,
    role_allows,
)
from app.audit_events import audit_log
from app.main import app


def _users():
    roles = {
        "admin": "admin",
        "operator": "operator",
        "alice": "analyst",
        "bob": "analyst",
        "viewer": "viewer",
    }
    return [
        {"username": name, "password_hash": hash_password(f"{name}-long-password"), "role": role}
        for name, role in roles.items()
    ]


class AuthorizationPrimitivesTests(unittest.TestCase):
    def setUp(self):
        ownership_registry.clear()

    def tearDown(self):
        ownership_registry.clear()

    def test_role_hierarchy_is_ordered_and_denies_unknown_roles(self):
        for role in ("viewer", "analyst", "operator", "admin"):
            self.assertTrue(role_allows(role, "viewer"))
        self.assertTrue(role_allows("admin", "admin"))
        self.assertFalse(role_allows("viewer", "operator"))
        self.assertFalse(role_allows("analyst", "admin"))
        self.assertFalse(role_allows("superuser", "viewer"))
        self.assertFalse(role_allows(None, "viewer"))
        self.assertFalse(role_allows("admin", "superuser"))

    def test_deny_by_default_without_actor(self):
        decision = authorize(None, "viewer")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "authentication_required")
        self.assertFalse(authorize({"username": "x", "role": None}, "viewer").allowed)

    def test_ownership_blocks_cross_user_access_but_admin_can_override(self):
        ownership_registry.record("layout", "layout-1", "alice")
        alice = {"username": "alice", "role": "analyst"}
        bob = {"username": "bob", "role": "analyst"}
        admin = {"username": "admin", "role": "admin"}
        ref = ResourceRef("layout", "layout-1")

        self.assertTrue(authorize(alice, "viewer", resource=ref).allowed)
        denied = authorize(bob, "viewer", resource=ref)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "not_resource_owner")
        self.assertTrue(authorize(admin, "viewer", resource=ref).allowed)

    def test_memory_and_task_resources_use_the_same_ownership_rule(self):
        ownership_registry.record("memory", "mem-1", "alice")
        ownership_registry.record("task", "task-1", "alice")
        alice = {"username": "alice", "role": "viewer"}
        bob = {"username": "bob", "role": "viewer"}
        for resource in (ResourceRef("memory", "mem-1"), ResourceRef("task", "task-1")):
            self.assertTrue(authorize(alice, "viewer", resource=resource).allowed)
            self.assertFalse(authorize(bob, "viewer", resource=resource).allowed)

    def test_path_policy_maps_sensitive_endpoints(self):
        self.assertEqual(required_role_for_path("/api/environment-validation")[0], "admin")
        self.assertEqual(required_role_for_path("/api/admin/users")[0], "admin")
        self.assertEqual(required_role_for_path("/api/backup/status")[0], "admin")
        self.assertEqual(required_role_for_path("/api/security/audit-events")[0], "operator")
        self.assertEqual(
            required_role_for_path("/api/workers/w/memory/m/review", "POST")[0], "operator"
        )
        self.assertEqual(required_role_for_path("/api/instrument-master/identifiers")[0], "analyst")
        self.assertEqual(required_role_for_path("/api/market-data/store")[0], "analyst")
        self.assertEqual(required_role_for_path("/api/market-data/import-csv")[0], "analyst")
        self.assertEqual(required_role_for_path("/api/workflows/execute")[0], "analyst")
        self.assertIsNone(required_role_for_path("/api/markets"))
        self.assertIsNone(required_role_for_path("/api/audit/events"))


class DurableOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            "os.environ", {"MARKET_MIND_DB": str(Path(self.tmp.name) / "ownership.db")}
        )
        self.env.start()
        ownership_registry.clear()

    def tearDown(self):
        ownership_registry.clear()
        self.env.stop()
        self.tmp.cleanup()

    def test_ownership_survives_a_new_registry_instance(self):
        from app.authorization import OwnershipRegistry
        ownership_registry.record("layout", "durable-1", "alice")
        restarted = OwnershipRegistry()
        self.assertEqual(restarted.owner_of("layout", "durable-1"), "alice")
        self.assertTrue(
            restarted.is_owner({"username": "alice", "role": "viewer"}, "layout", "durable-1")
        )
        self.assertFalse(
            restarted.is_owner({"username": "bob", "role": "viewer"}, "layout", "durable-1")
        )

    def test_unregistered_resource_is_not_globally_owned(self):
        decision = authorize(
            {"username": "alice", "role": "viewer"}, "viewer",
            resource=ResourceRef("layout", "never-claimed"),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unregistered_resource")


class SharedBearerPrivilegeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict("os.environ", {
            "MARKET_MIND_DB": str(Path(self.tmp.name) / "bearer.db"),
            "MARKET_MIND_USER_AUTH": "false",
            "API_AUTH_REQUIRED": "true",
            "API_AUTH_TOKEN": "t" * 48,
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_bearer_holder_is_not_administrator(self):
        client = TestClient(app)
        headers = {"Authorization": "Bearer " + "t" * 48}
        self.assertEqual(client.get("/api/admin/users", headers=headers).status_code, 403)
        self.assertEqual(
            client.get("/api/security/audit-events", headers=headers).status_code, 403
        )
        self.assertEqual(client.get("/api/health").status_code, 200)


class AuthorizationApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "auth.db"
        self.env = {
            "MARKET_MIND_USER_AUTH": "true",
            "MARKET_MIND_USERS": json.dumps(_users()),
            "MARKET_MIND_DB": str(self.db),
        }
        ownership_registry.clear()
        audit_log.clear()
        self._env_patcher = patch.dict("os.environ", self.env, clear=False)
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()
        self.tmp.cleanup()
        ownership_registry.clear()
        audit_log.clear()

    def _login(self, username: str):
        client = TestClient(app)
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": f"{username}-long-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return client, response.json()["csrf_token"]

    def test_viewer_cannot_call_operator_or_admin_endpoints(self):
        viewer, csrf = self._login("viewer")
        self.assertEqual(viewer.get("/api/admin/users").status_code, 403)
        self.assertEqual(viewer.get("/api/environment-validation").status_code, 403)
        self.assertEqual(viewer.get("/api/security/audit-events").status_code, 403)
        self.assertEqual(
            viewer.post(
                "/api/workers/worker_001/memory/memory_001/review",
                headers={"X-CSRF-Token": csrf},
                json={"decision": "approved", "reviewer": "viewer"},
            ).status_code,
            403,
        )
        operator, _ = self._login("operator")
        self.assertEqual(operator.get("/api/security/audit-events").status_code, 200)
        admin, _ = self._login("admin")
        self.assertEqual(admin.get("/api/admin/users").status_code, 200)
        self.assertEqual(admin.get("/api/environment-validation").status_code, 200)

    def test_viewer_cannot_store_market_data_and_analyst_can(self):
        payload = {
            "symbol": "AAPL", "interval": "1d", "status": "historical",
            "source": "manual-review", "retrieved_at": "2026-01-01T00:00:00Z",
            "bars": [],
        }
        viewer, csrf = self._login("viewer")
        denied = viewer.post(
            "/api/market-data/store", headers={"X-CSRF-Token": csrf}, json=payload
        )
        self.assertEqual(denied.status_code, 403)
        analyst, analyst_csrf = self._login("alice")
        allowed = analyst.post(
            "/api/market-data/store", headers={"X-CSRF-Token": analyst_csrf}, json=payload
        )
        self.assertNotEqual(allowed.status_code, 403)

    def test_cross_user_layout_access_is_denied(self):
        alice, csrf = self._login("alice")
        created = alice.post(
            "/api/workspaces",
            headers={"X-CSRF-Token": csrf},
            json={"title": "Alice layout", "description": "", "nodes": [], "edges": []},
        )
        self.assertEqual(created.status_code, 200, created.text)
        layout_id = created.json()["id"]

        bob, bob_csrf = self._login("bob")
        self.assertEqual(bob.get(f"/api/workspaces/{layout_id}").status_code, 403)
        self.assertEqual(
            bob.delete(f"/api/workspaces/{layout_id}", headers={"X-CSRF-Token": bob_csrf}).status_code,
            403,
        )
        self.assertNotIn(layout_id, [item["id"] for item in bob.get("/api/workspaces").json()["workflows"]])
        self.assertEqual(alice.get(f"/api/workspaces/{layout_id}").status_code, 200)

    def test_cross_user_watchlist_mutation_is_denied(self):
        alice, csrf = self._login("alice")
        added = alice.post(
            "/api/watchlist", headers={"X-CSRF-Token": csrf}, json={"symbol": "btcusd"}
        )
        self.assertEqual(added.status_code, 200, added.text)
        bob, bob_csrf = self._login("bob")
        self.assertEqual(
            bob.delete("/api/watchlist/BTCUSD", headers={"X-CSRF-Token": bob_csrf}).status_code,
            403,
        )
        self.assertEqual(bob.get("/api/watchlist").json()["count"], 0)
        self.assertEqual(
            alice.delete("/api/watchlist/BTCUSD", headers={"X-CSRF-Token": csrf}).status_code,
            200,
        )

    def test_missing_and_duplicate_csrf_tokens_are_rejected(self):
        client, csrf = self._login("alice")
        self.assertEqual(client.post("/api/watchlist", json={"symbol": "ethusd"}).status_code, 403)
        duplicated = client.post(
            "/api/watchlist",
            headers={"X-CSRF-Token": csrf, "x-csrf-token": csrf},
            json={"symbol": "ethusd"},
        )
        self.assertEqual(duplicated.status_code, 403)
        accepted = client.post(
            "/api/watchlist", headers={"X-CSRF-Token": csrf}, json={"symbol": "ethusd"}
        )
        self.assertEqual(accepted.status_code, 200)

    def test_login_revokes_preexisting_session(self):
        from app import user_auth

        old = user_auth.create_user_session({"username": "viewer", "role": "viewer"}, self.env)
        client = TestClient(app)
        client.cookies.set(user_auth.SESSION_COOKIE, old["session_token"])
        response = client.post(
            "/api/auth/login", json={"username": "alice", "password": "alice-long-password"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(user_auth.get_user_session(old["session_token"], self.env))
        self.assertNotEqual(response.json()["csrf_token"], old["csrf_token"])

    def test_auth_disabled_keeps_public_and_write_endpoints_working(self):
        with patch.dict("os.environ", {"MARKET_MIND_USER_AUTH": "false"}, clear=False):
            client = TestClient(app)
            self.assertEqual(client.get("/api/markets").status_code, 200)
            self.assertEqual(client.get("/api/environment-validation").status_code, 200)
            self.assertEqual(client.post("/api/watchlist", json={"symbol": "solusd"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
