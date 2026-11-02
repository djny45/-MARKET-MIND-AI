import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.worker_memory import read_memory


class ProposalReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "review.sqlite")
        })
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _create_proposal(self, worker_id="worker_001"):
        response = self.client.post(
            f"/api/analytical-agents/{worker_id}/update-proposals",
            json={
                "title": "Improve source validation",
                "rationale": "Current citations need an explicit review gate.",
                "proposed_change": "Add source validation before publishing summaries.",
                "evidence_refs": ["test:source-validation"],
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["memory_id"]

    def _review_payload(self, **overrides):
        payload = {
            "reviewer": "human-reviewer",
            "decision": "approve",
            "review_note": "Reviewed the proposal and its scope.",
            "tests_checked": True,
            "rollback_plan": "Revert the associated commit and rerun the test suite.",
        }
        payload.update(overrides)
        return payload

    def test_approval_records_review_without_applying_or_mutating_proposal(self):
        proposal_id = self._create_proposal()
        before = read_memory("worker_001", "method_note", 200)["memory"]
        proposal = next(x for x in before if x["memory_id"] == proposal_id)

        response = self.client.post(
            f"/api/analytical-agents/worker_001/update-proposals/{proposal_id}/review",
            json=self._review_payload(),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "review_recorded")
        self.assertFalse(body["applied"])
        self.assertFalse(body["auto_apply"])
        self.assertFalse(body["proposal_changed"])
        self.assertEqual(body["review"]["decision"], "approve")
        self.assertEqual(body["review"]["proposal_content_sha256"], 
                         self.client.get("/api/analytical-agents/worker_001/update-proposals").json()["proposals"][0]["content_sha256"])

        after = read_memory("worker_001", "method_note", 200)["memory"]
        unchanged = next(x for x in after if x["memory_id"] == proposal_id)
        self.assertEqual(unchanged["content"], proposal["content"])
        reviews = read_memory("worker_001", "validation_result", 200)["memory"]
        self.assertEqual(reviews[0]["content"]["proposal_review"]["proposal_id"], proposal_id)

    def test_reject_decision_is_append_only_and_supported(self):
        proposal_id = self._create_proposal()
        response = self.client.post(
            f"/api/analytical-agents/worker_001/update-proposals/{proposal_id}/review",
            json=self._review_payload(decision="reject", review_note="Evidence is insufficient."),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["review"]["decision"], "reject")
        self.assertFalse(response.json()["applied"])

    def test_unknown_or_cross_worker_proposal_is_not_reviewable(self):
        proposal_id = self._create_proposal("worker_001")
        response = self.client.post(
            f"/api/analytical-agents/worker_002/update-proposals/{proposal_id}/review",
            json=self._review_payload(),
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_decision_and_missing_required_review_fields_rejected(self):
        proposal_id = self._create_proposal()
        base = f"/api/analytical-agents/worker_001/update-proposals/{proposal_id}/review"
        self.assertEqual(
            self.client.post(base, json=self._review_payload(decision="maybe")).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(base, json=self._review_payload(rollback_plan=" ")).status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
