import os
import tempfile
import unittest
from unittest.mock import patch

from app.workspace import save_synthesis_review, get_synthesis_review, list_synthesis_reviews, synthesis_review_summary


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


    def test_citation_provenance_survives_sqlite_round_trip_and_digest(self):
        from app.synthesis_review import build_synthesis_review
        review = build_synthesis_review(
            draft="Review draft with a citation.",
            claims=[{
                "text": "Claim supported by source excerpt.",
                "source_refs": ["source-1"],
                "citations": [{
                    "source_id": "source-1",
                    "excerpt": "exact source passage",
                }],
            }],
            source_registry=[{
                "source_id": "source-1",
                "text": "Opening. exact source passage. Closing.",
            }],
            decision="reject",
            reviewer="human-reviewer",
            review_note="Needs semantic verification.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "citation.db")}):
                saved = save_synthesis_review(review)
                fetched = get_synthesis_review(saved["review_id"])
        self.assertTrue(fetched["integrity"]["verified"])
        self.assertEqual(fetched["citation_audit"], review["citation_audit"])
        self.assertEqual(fetched["citation_gate"], review["citation_gate"])
        citation = fetched["citation_audit"]["claims"][0]["citations"][0]
        self.assertEqual(citation["excerpt"], "exact source passage")
        self.assertIn("does not establish semantic support", fetched["citation_gate"]["note"])

    def test_validated_claim_checklist_survives_review_history_round_trip(self):
        from app.synthesis_review import validate_claim_review_checklist
        checklist = validate_claim_review_checklist([{
            "claim_index": 0,
            "semantic_assessment": "faithful_paraphrase",
            "reviewer_checked_source_context": True,
            "reviewer_checked_counterevidence": True,
            "reviewer_note": "Compared the source context and counterevidence.",
            "review_complete": True,
        }])
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "checklist.db")}):
                saved = save_synthesis_review({
                    "status": "rejected", "reviewer": "claimed-reviewer",
                    "draft": "Checklist review draft.",
                    "claim_review_checklist": checklist,
                })
                fetched = get_synthesis_review(saved["review_id"])
        self.assertTrue(fetched["integrity"]["verified"])
        self.assertEqual(fetched["claim_review_checklist"], checklist)
        self.assertEqual(fetched["claim_review_checklist"]["status"], "complete")
        self.assertEqual(fetched["claim_review_checklist"]["complete_claim_count"], 1)


    def test_review_history_filters_and_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "filtered.db")}):
                save_synthesis_review({"status": "approved", "reviewer": "alice", "draft": "private A"})
                save_synthesis_review({"status": "rejected", "reviewer": "alice", "draft": "private B"})
                save_synthesis_review({"status": "approved", "reviewer": "bob", "draft": "private C"})
                approved_alice = list_synthesis_reviews(status="approved", reviewer="alice")
                summary = synthesis_review_summary()
                alice_summary = synthesis_review_summary(reviewer="alice")
        self.assertEqual(len(approved_alice), 1)
        self.assertEqual(approved_alice[0]["status"], "approved")
        self.assertNotIn("draft", approved_alice[0])
        self.assertEqual(summary, {"total": 3, "by_status": {"approved": 2, "rejected": 1}})
        self.assertEqual(alice_summary, {"total": 2, "by_status": {"approved": 1, "rejected": 1}})

    def test_review_history_rejects_invalid_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(tmp, "invalid-filter.db")}):
                save_synthesis_review({"status": "approved", "reviewer": "alice"})
                with self.assertRaisesRegex(ValueError, "status"):
                    list_synthesis_reviews(status=" ")
                with self.assertRaisesRegex(ValueError, "reviewer"):
                    synthesis_review_summary(reviewer=" ")



if __name__ == "__main__":
    unittest.main()
