import unittest

from app.synthesis_review import build_synthesis_review


class SynthesisReviewTests(unittest.TestCase):
    def setUp(self):
        self.base = dict(
            draft="Draft summary for review.",
            claims=[{"text": "Claim from supplied source.", "source_refs": ["src-1"]}],
            source_registry=[{"source_id": "src-1", "title": "Imported report"}],
            reviewer="human-reviewer",
        )

    def test_approval_requires_refs_matching_supplied_registry(self):
        result = build_synthesis_review(**self.base, decision="approve")
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["claims"][0]["reference_check"], "matched_registry")
        self.assertFalse(result["claims"][0]["source_authenticity_verified"])

    def test_approval_rejects_missing_source_refs(self):
        args = dict(self.base)
        args["claims"] = [{"text": "Uncited claim.", "source_refs": []}]
        with self.assertRaisesRegex(ValueError, "Approval blocked"):
            build_synthesis_review(**args, decision="approve")

    def test_approval_rejects_unknown_source_id(self):
        args = dict(self.base)
        args["claims"] = [{"text": "Claim.", "source_refs": ["not-in-registry"]}]
        with self.assertRaisesRegex(ValueError, "Approval blocked"):
            build_synthesis_review(**args, decision="approve")

    def test_rejection_can_record_unverified_claim(self):
        args = dict(self.base)
        args["claims"] = [{"text": "Uncited.", "source_refs": []}]
        result = build_synthesis_review(**args, decision="reject", review_note="Needs evidence")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["evidence_status"], "incomplete_source_refs")

    def test_invalid_decision_and_bounds_rejected(self):
        with self.assertRaisesRegex(ValueError, "decision"):
            build_synthesis_review(**self.base, decision="auto-approve")
        args = dict(self.base)
        args["draft"] = "x" * 8001
        with self.assertRaisesRegex(ValueError, "draft"):
            build_synthesis_review(**args, decision="reject")


if __name__ == "__main__":
    unittest.main()
