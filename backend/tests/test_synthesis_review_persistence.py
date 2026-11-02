import os
import tempfile
import unittest
from unittest.mock import patch

from app.workspace import save_synthesis_review


class SynthesisReviewPersistenceTests(unittest.TestCase):
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
