import os
import tempfile
import unittest
from app.worker_memory import store_worker_memory
from app.shared_knowledge import review_worker_memory, list_shared_knowledge

class SharedKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("MARKET_MIND_DB")
        os.environ["MARKET_MIND_DB"] = os.path.join(self.tmp.name, "test.db")

    def tearDown(self):
        if self.old is None: os.environ.pop("MARKET_MIND_DB", None)
        else: os.environ["MARKET_MIND_DB"] = self.old
        self.tmp.cleanup()

    def test_approval_promotes_note_to_shared_store(self):
        note = store_worker_memory("worker_001","observation","Fixture observation",
                                   ["fixture://one"],"synthetic")
        result = review_worker_memory("worker_001",note["memory_id"],"approve","human-reviewer")
        self.assertEqual(result["review_status"],"approved")
        shared = list_shared_knowledge()
        self.assertEqual(shared["count"],1)
        self.assertEqual(shared["entries"][0]["source_refs"],["fixture://one"])

    def test_rejection_does_not_promote_note(self):
        note = store_worker_memory("worker_001","methodology","Method note")
        result = review_worker_memory("worker_001",note["memory_id"],"reject","human-reviewer","insufficient")
        self.assertEqual(result["review_status"],"rejected")
        self.assertEqual(list_shared_knowledge()["count"],0)

    def test_second_review_is_blocked(self):
        note = store_worker_memory("worker_001","observation","One")
        review_worker_memory("worker_001",note["memory_id"],"approve","reviewer")
        with self.assertRaises(ValueError):
            review_worker_memory("worker_001",note["memory_id"],"approve","reviewer")

if __name__ == "__main__":
    unittest.main()
