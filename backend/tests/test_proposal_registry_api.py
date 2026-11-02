import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.worker_memory import append_memory


class ProposalRegistryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "proposals.sqlite")
        })
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_registry_returns_stable_id_hash_and_review_only_metadata(self):
        record = append_memory("worker_001", "method_note", {
            "update_proposal": {
                "title": "Improve citation checks",
                "status": "pending_review",
                "auto_apply": False,
            }
        })
        response = self.client.get("/api/analytical-agents/worker_001/update-proposals")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        item = body["proposals"][0]
        self.assertEqual(item["proposal_id"], record["memory_id"])
        self.assertEqual(item["version"], 1)
        self.assertEqual(len(item["content_sha256"]), 64)
        self.assertFalse(item["auto_apply"])

    def test_registry_rejects_unknown_worker_and_invalid_limit(self):
        self.assertEqual(
            self.client.get("/api/analytical-agents/unknown/update-proposals").status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/api/analytical-agents/worker_001/update-proposals?limit=0").status_code,
            400,
        )


if __name__ == "__main__":
    unittest.main()
