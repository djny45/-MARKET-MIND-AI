import os
import tempfile
import unittest
from unittest.mock import patch

from app.worker_memory import list_worker_memory, store_worker_memory
from app.main import WorkerMemoryRequest, add_worker_memory, get_worker_memory


class WorkerMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "workers.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_store_and_read_scoped_evidence_note(self):
        saved = store_worker_memory(
            "worker_001", "observation", "Daily trend calculation completed.",
            ["import:batch-01"], "partial",
        )
        result = list_worker_memory("worker_001")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["memory_id"], saved["memory_id"])
        self.assertEqual(result["entries"][0]["source_refs"], ["import:batch-01"])
        self.assertEqual(result["entries"][0]["review_status"], "pending_review")
        self.assertEqual(result["memory_policy"], "append_only_pending_review")

    def test_memory_is_isolated_between_workers(self):
        store_worker_memory("worker_001", "observation", "Worker one note.")
        store_worker_memory("worker_002", "methodology", "Worker two method.")
        self.assertEqual(list_worker_memory("worker_001")["count"], 1)
        self.assertEqual(list_worker_memory("worker_002")["count"], 1)

    def test_unreviewed_shared_knowledge_type_is_rejected(self):
        with self.assertRaises(ValueError):
            store_worker_memory("worker_001", "reviewed_lesson", "Not supported.")

    def test_invalid_worker_and_evidence_are_rejected(self):
        with self.assertRaises(KeyError):
            store_worker_memory("worker_999", "observation", "Unknown worker.")
        with self.assertRaises(ValueError):
            store_worker_memory("worker_001", "observation", "  ")
        with self.assertRaises(ValueError):
            store_worker_memory("worker_001", "observation", "Valid", [""])


    def test_api_memory_endpoints_preserve_worker_scope(self):
        request = WorkerMemoryRequest(
            memory_type="observation",
            content="API stored observation.",
            source_refs=["api:source-01"],
            quality_status="unverified",
        )
        saved = add_worker_memory("worker_003", request)
        result = get_worker_memory("worker_003", 20, None)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["memory_id"], saved["memory_id"])

    def test_type_filter_and_limit_validation(self):
        store_worker_memory("worker_001", "observation", "Observation.")
        store_worker_memory("worker_001", "methodology", "Method.")
        result = list_worker_memory("worker_001", memory_type="methodology")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["memory_type"], "methodology")
        with self.assertRaises(ValueError):
            list_worker_memory("worker_001", limit=0)


    def test_explicit_human_approval_promotes_evidence_linked_memory(self):
        from app.worker_memory import review_worker_memory, list_shared_knowledge
        entry = store_worker_memory(
            "worker_001", "observation", "Reference note", ["source:fixture-1"], "partial"
        )
        reviewed = review_worker_memory(
            entry["memory_id"], "approve", "local-reviewer", "Checked source reference and context."
        )
        self.assertEqual(reviewed["review_status"], "approved")
        self.assertTrue(reviewed["shared_knowledge_created"])
        self.assertFalse(reviewed["reviewer_identity_authenticated"])
        shared = list_shared_knowledge()
        self.assertTrue(any(item["memory_id"] == entry["memory_id"] for item in shared["entries"]))

    def test_synthetic_or_unreferenced_memory_cannot_be_promoted(self):
        from app.worker_memory import review_worker_memory
        synthetic = store_worker_memory("worker_001", "observation", "Synthetic", [], "synthetic")
        with self.assertRaisesRegex(ValueError, "source reference"):
            review_worker_memory(synthetic["memory_id"], "approve", "reviewer", "reviewed")
        unreferenced = store_worker_memory("worker_001", "observation", "No refs", [], "partial")
        with self.assertRaisesRegex(ValueError, "source reference"):
            review_worker_memory(unreferenced["memory_id"], "approve", "reviewer", "reviewed")


if __name__ == "__main__":
    unittest.main()
