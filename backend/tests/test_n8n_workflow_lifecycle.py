import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

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
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "lifecycle.db")}):
            # This payload represents the workflow export produced by an agent authoring step.
            created = create_n8n_workflow_draft(N8NWorkflowDraftRequest(
                agent_id="research-agent-01", title="Research intake", workflow=authored_export(),
            ))
            self.assertEqual(created["status"], "pending_human_review")
            self.assertTrue(created["validation"]["structurally_valid"])
            self.assertTrue(created["human_review_required"])
            self.assertFalse(created["auto_approval"])
            self.assertFalse(created["workflow_activation"])

            pending = list_n8n_workflow_drafts(status="pending_human_review")
            self.assertEqual([item["draft_id"] for item in pending], [created["draft_id"]])

            decision = review_n8n_workflow_draft(
                created["draft_id"],
                N8NWorkflowReviewRequest(reviewer="operator-reviewer", decision="approve", review_note="Reviewed node scope and connections."),
            )
            self.assertEqual(decision["status"], "approved")
            self.assertFalse(decision["reviewer_identity_verified"])
            self.assertFalse(decision["workflow_execution"])

            stored = read_n8n_workflow_draft(created["draft_id"])
            self.assertEqual(stored["status"], "approved")
            self.assertEqual(stored["workflow"], authored_export())
            self.assertEqual(stored["review"]["decision"], "approve")
            self.assertEqual(stored["workflow_sha256"], decision["workflow_sha256"])

    def test_invalid_generated_export_never_enters_review_queue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "invalid.db")}):
            workflow = authored_export()
            workflow["active"] = True
            with self.assertRaises(HTTPException) as raised:
                create_n8n_workflow_draft(N8NWorkflowDraftRequest(
                    agent_id="research-agent-01", title="Unsafe active export", workflow=workflow,
                ))
            self.assertEqual(raised.exception.status_code, 422)
            self.assertEqual(list_n8n_workflow_drafts(), {"drafts": []})

    def test_review_is_single_decision_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "single-review.db")}):
            created = create_n8n_workflow_draft(N8NWorkflowDraftRequest(
                agent_id="research-agent-02", title="Candidate", workflow=authored_export(),
            ))
            review_n8n_workflow_draft(created["draft_id"], N8NWorkflowReviewRequest(
                reviewer="reviewer", decision="reject", review_note="Missing owner documentation.",
            ))
            with self.assertRaises(HTTPException) as raised:
                review_n8n_workflow_draft(created["draft_id"], N8NWorkflowReviewRequest(
                    reviewer="reviewer", decision="approve",
                ))
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(read_n8n_workflow_draft(created["draft_id"])["status"], "rejected")

    def test_unknown_draft_returns_not_found(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "missing.db")}):
            with self.assertRaises(HTTPException) as raised:
                review_n8n_workflow_draft("missing", N8NWorkflowReviewRequest(
                    reviewer="reviewer", decision="approve",
                ))
            self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
