import os
import tempfile
import unittest
from unittest.mock import patch

from app.workspace import save_synthesis_review, get_synthesis_review, list_synthesis_reviews


class SynthesisReviewPersistenceTests(unittest.TestCase):
    def test_review_history_retrieval_verifies_digest_and_lists_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "history.db")}):
                saved = save_synthesis_review({
                    "status": "rejected", "reviewer": "reviewer-label",
                    "draft": "snapshot text", "claims": [{"text": "fixture"}],
                })
                fetched = get_synthesis_review(saved["review_id"])
                listing = list_synthesis_reviews(limit=10)
        self.assertTrue(saved["integrity"]["verified"])
        self.assertTrue(fetched["integrity"]["verified"])
        self.assertEqual(fetched["draft"], "snapshot text")
        self.assertEqual(listing[0]["review_id"], saved["review_id"])
        self.assertNotIn("draft", listing[0])

    def test_review_history_reports_missing_record_and_invalid_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "missing.db")}):
                self.assertIsNone(get_synthesis_review("missing-review"))
                with self.assertRaisesRegex(ValueError, "limit"):
                    list_synthesis_reviews(limit=0)

    def test_review_is_persisted_as_append_only_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "reviews.db")}):
                first = save_synthesis_review({
                    "status": "approved", "reviewer": "claimed-reviewer",
                    "draft": "draft", "claims": [],
                })
                second = save_synthesis_review({
                    "status": "rejected", "reviewer": "claimed-reviewer",
                    "draft": "another draft", "claims": [],
                })
        self.assertNotEqual(first["review_id"], second["review_id"])
        self.assertEqual(first["review_persistence"], "append_only_record")
        self.assertEqual(first["status"], "approved")
        self.assertEqual(second["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
