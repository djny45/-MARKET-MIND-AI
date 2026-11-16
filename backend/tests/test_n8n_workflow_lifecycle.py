import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.security import HTTPAuthorizationCredentials

from fastapi import HTTPException

AUTH_TOKEN = "reviewer-token-for-tests-0000000000000000000000000000000000000000"
AUTH_ENV = {"N8N_REVIEWER_TOKENS_JSON": __import__("json").dumps({"operator-reviewer": {"token": AUTH_TOKEN, "roles": ["reviewer"]}})}
AUTH = HTTPAuthorizationCredentials(scheme="Bearer", credentials=AUTH_TOKEN)

from app.main import (
    N8NWorkflowDraftRequest, N8NWorkflowReviewRequest,
    create_n8n_workflow_draft, review_n8n_workflow_draft,
    read_n8n_workflow_draft, list_n8n_workflow_drafts,
)


def authored_export():
    return {
        "name": "Research intake",
        "active": False,
        "nodes": [
            {"id": "n1", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "parameters": {}},
            {"id": "n2", "name": "Normalize", "type": "n8n-nodes-base.set", "typeVersion": 3, "parameters": {}},
        ],
        "connections": {
            "Manual Trigger": {"main": [[{"node": "Normalize", "type": "main", "index": 0}]]}
        },
    }


class N8NWorkflowAuthoringLifecycleTests(unittest.TestCase):
    def test_generate_validate_review_approve_flow_persists_full_audit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "lifecycle.db"), **AUTH_ENV}):
            # This payload represents the workflow export produced by an agent authoring step.
            created = create_n8n_workflow_draft(N8NWorkflowDraftRequest(
                agent_id="research-agent-01", title="Research intake", workflow=authored_export(),
            ))
            self.assertEqual(created["status"], "pending_human_review")
            self.assertTrue(created["validation"]["structurally_valid"])
            self.assertTrue(created["human_review_required"])
            self.assertFalse(created["auto_approval"])
            self.assertFalse(created["workflow_activation"])

            pending = list_n8n_workflow_drafts(status="pending_human_review", credentials=AUTH)
            self.assertEqual([item["draft_id"] for item in pending["drafts"]], [created["draft_id"]])

            decision = review_n8n_workflow_draft(
                created["draft_id"],
                N8NWorkflowReviewRequest(decision="approve", review_note="Reviewed node scope and connections."), credentials=AUTH,
            )
            self.assertEqual(decision["status"], "approved")
            self.assertTrue(decision["reviewer_identity_verified"])
            self.assertEqual(decision["reviewer"], "operator-reviewer")
            self.assertFalse(decision["workflow_execution"])

            stored = read_n8n_workflow_draft(created["draft_id"], credentials=AUTH)
            self.assertEqual(stored["status"], "approved")
            self.assertEqual(stored["workflow"], authored_export())
            self.assertEqual(stored["review"]["decision"], "approve")
            self.assertTrue(stored["review"]["reviewer_identity_verified"])
            self.assertEqual(stored["review"]["reviewer"], "operator-reviewer")
            self.assertEqual(stored["workflow_sha256"], decision["workflow_sha256"])

    def test_invalid_generated_export_never_enters_review_queue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "invalid.db"), **AUTH_ENV}):
            workflow = authored_export()
            workflow["active"] = True
            with self.assertRaises(HTTPException) as raised:
                create_n8n_workflow_draft(N8NWorkflowDraftRequest(
                    agent_id="research-agent-01", title="Unsafe active export", workflow=workflow,
                ))
            self.assertEqual(raised.exception.status_code, 422)
            self.assertEqual(list_n8n_workflow_drafts(credentials=AUTH), {"drafts": []})

    def test_review_is_single_decision_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "single-review.db"), **AUTH_ENV}):
            created = create_n8n_workflow_draft(N8NWorkflowDraftRequest(
                agent_id="research-agent-02", title="Candidate", workflow=authored_export(),
            ))
            review_n8n_workflow_draft(created["draft_id"], N8NWorkflowReviewRequest(
                decision="reject", review_note="Missing owner documentation.",
            ), credentials=AUTH)
            with self.assertRaises(HTTPException) as raised:
                review_n8n_workflow_draft(created["draft_id"], N8NWorkflowReviewRequest(decision="approve"), credentials=AUTH)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(read_n8n_workflow_draft(created["draft_id"], credentials=AUTH)["status"], "rejected")

    def test_unknown_draft_returns_not_found(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "missing.db"), **AUTH_ENV}):
            with self.assertRaises(HTTPException) as raised:
                review_n8n_workflow_draft("missing", N8NWorkflowReviewRequest(decision="approve"), credentials=AUTH)
            self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
