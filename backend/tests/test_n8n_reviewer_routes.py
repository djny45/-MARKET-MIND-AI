import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


REVIEWER_TOKEN = "reviewer-api-token-000000000000000000000000000000000000"
IMPORTER_TOKEN = "importer-api-token-000000000000000000000000000000000000"
REVIEWER_ONLY = {
    "reviewer-a": {"token": REVIEWER_TOKEN, "roles": ["reviewer"]},
}
IMPORTER_ONLY = {
    "importer-a": {"token": IMPORTER_TOKEN, "roles": ["importer"]},
}
BOTH_ROLES = {
    "reviewer-a": {"token": REVIEWER_TOKEN, "roles": ["reviewer"]},
    "importer-a": {"token": IMPORTER_TOKEN, "roles": ["importer"]},
}


def workflow_export():
    return {
        "name": "HTTP route security fixture",
        "active": False,
        "nodes": [
            {
                "id": "trigger",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "parameters": {},
            }
        ],
        "connections": {},
    }


class N8NReviewerRouteSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "MARKET_MIND_DB": os.path.join(self.tmp.name, "routes.sqlite"),
                "N8N_REVIEWER_TOKENS_JSON": json.dumps(BOTH_ROLES),
            },
        )
        self.env.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def _create_draft(self):
        response = self.client.post(
            "/api/n8n/workflows/drafts",
            json={
                "agent_id": "route-test-agent",
                "title": "Route security fixture",
                "workflow": workflow_export(),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["draft_id"]

    def _approve(self, draft_id):
        response = self.client.post(
            f"/api/n8n/workflows/drafts/{draft_id}/review",
            headers={"Authorization": f"Bearer {REVIEWER_TOKEN}"},
            json={"decision": "approve", "review_note": "Route authorization test."},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_review_queue_rejects_missing_and_invalid_bearer_tokens(self):
        draft_id = self._create_draft()
        missing = self.client.get("/api/n8n/workflows/drafts")
        invalid = self.client.get(
            f"/api/n8n/workflows/drafts/{draft_id}",
            headers={"Authorization": "Bearer " + "z" * 48},
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)

    def test_reviewer_can_read_and_review_but_cannot_import(self):
        draft_id = self._create_draft()
        headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}
        read = self.client.get(f"/api/n8n/workflows/drafts/{draft_id}", headers=headers)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.json()["status"], "pending_human_review")

        with patch("app.main.import_approved_workflow") as import_mock:
            denied = self.client.post(
                f"/api/n8n/workflows/drafts/{draft_id}/import",
                headers=headers,
            )
        self.assertEqual(denied.status_code, 403)
        import_mock.assert_not_called()

    def test_importer_can_import_role_gate_but_cannot_review(self):
        draft_id = self._create_draft()
        headers = {"Authorization": f"Bearer {IMPORTER_TOKEN}"}
        denied_review = self.client.post(
            f"/api/n8n/workflows/drafts/{draft_id}/review",
            headers=headers,
            json={"decision": "approve", "review_note": "Should be denied."},
        )
        self.assertEqual(denied_review.status_code, 403)

        with patch("app.main.import_approved_workflow") as import_mock:
            import_mock.return_value = {
                "draft_id": draft_id,
                "status": "imported_inactive",
                "workflow_activation": False,
                "workflow_execution": False,
            }
            # The draft is pending, so the import service must not be called by a real request.
            # Role authorization is checked before the service is invoked; approval remains mandatory.
            from app.n8n_reviewer_security import import_approved_workflow as real_import
            with patch("app.main.import_approved_workflow", wraps=real_import):
                denied_import = self.client.post(
                    f"/api/n8n/workflows/drafts/{draft_id}/import",
                    headers=headers,
                )
            self.assertEqual(denied_import.status_code, 409)

    def test_reviewer_can_approve_and_importer_role_is_separately_required(self):
        draft_id = self._create_draft()
        self._approve(draft_id)
        with patch("app.main.import_approved_workflow") as import_mock:
            import_mock.return_value = {
                "draft_id": draft_id,
                "status": "imported_inactive",
                "workflow_activation": False,
                "workflow_execution": False,
            }
            response = self.client.post(
                f"/api/n8n/workflows/drafts/{draft_id}/import",
                headers={"Authorization": f"Bearer {IMPORTER_TOKEN}"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        import_mock.assert_called_once_with(draft_id, "importer-a")
        self.assertFalse(response.json()["workflow_activation"])
        self.assertFalse(response.json()["workflow_execution"])

    def test_unconfigured_reviewer_authentication_fails_closed(self):
        with patch.dict(os.environ, {"N8N_REVIEWER_TOKENS_JSON": ""}):
            response = self.client.get("/api/n8n/workflows/drafts")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
