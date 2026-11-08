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

    def test_review_packet_flags_unknown_refs_and_requires_human_decision(self):
        from app.synthesis_review import build_synthesis_review_packet
        packet = build_synthesis_review_packet(
            draft="Review draft with caveat.",
            claims=[{"text": "Claim with unknown source", "source_refs": ["missing-id"]}],
            source_registry=[{"source_id": "known-id"}],
        )
        self.assertEqual(packet["review_status"], "pending_human_decision")
        self.assertEqual(packet["reference_gate"]["status"], "blocked")
        self.assertTrue(packet["human_decision_required"])
        self.assertFalse(packet["auto_approval"])
        self.assertEqual(packet["evidence_audit"]["metrics"]["unknown_source_id_count"], 1)

    def test_review_packet_passes_reference_gate_but_never_verifies_truth(self):
        from app.synthesis_review import build_synthesis_review_packet
        packet = build_synthesis_review_packet(
            draft="A sourced claim; limitation: source meaning is not verified.",
            claims=[{"text": "Claim", "source_refs": ["src-1"]}],
            source_registry=[{"source_id": "src-1"}],
        )
        self.assertEqual(packet["reference_gate"]["status"], "passed")
        self.assertFalse(packet["auto_approval"])
        self.assertTrue(any("not that sources substantiate claims" in item for item in packet["limitations"]))


    def test_review_packet_integrates_exact_citation_audit(self):
        from app.synthesis_review import build_synthesis_review_packet
        packet = build_synthesis_review_packet(
            draft="Draft with a traceable quote.",
            claims=[{
                "text": "Claim supported by an excerpt.",
                "source_refs": ["s1"],
                "citations": [{"source_id": "s1", "excerpt": "verbatim excerpt"}],
            }],
            source_registry=[{
                "source_id": "s1", "text": "Intro. verbatim excerpt. Outro.",
            }],
        )
        self.assertEqual(packet["citation_audit"]["status"], "passed")
        self.assertEqual(packet["citation_gate"]["claim_citation_coverage"], 1.0)
        self.assertEqual(packet["citation_gate"]["claims_without_valid_citations"], 0)
        self.assertEqual(packet["review_status"], "pending_human_decision")
        self.assertTrue(packet["human_decision_required"])
        self.assertFalse(packet["auto_approval"])

    def test_review_packet_flags_missing_or_bad_citation_excerpt(self):
        from app.synthesis_review import build_synthesis_review_packet
        packet = build_synthesis_review_packet(
            draft="Review citation gap.",
            claims=[{
                "text": "Claim without usable citation.",
                "source_refs": ["s1"],
                "citations": [{"source_id": "s1", "excerpt": "not present"}],
            }],
            source_registry=[{"source_id": "s1", "text": "source text here"}],
        )
        self.assertEqual(packet["citation_audit"]["status"], "needs_review")
        self.assertEqual(packet["citation_gate"]["claims_without_valid_citations"], 1)
        self.assertEqual(packet["review_status"], "pending_human_decision")
        self.assertFalse(packet["auto_approval"])

    def test_review_packet_missing_citation_metadata_needs_review(self):
        from app.synthesis_review import build_synthesis_review_packet
        packet = build_synthesis_review_packet(
            draft="Claim needs citation review.",
            claims=[{"text": "Claim with source ref but no excerpt citations.", "source_refs": ["s1"]}],
            source_registry=[{"source_id": "s1", "text": "Some source text."}],
        )
        self.assertEqual(packet["citation_audit"]["status"], "needs_review")
        self.assertEqual(packet["citation_gate"]["claims_without_valid_citations"], 1)

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


    def test_review_result_preserves_citation_audit_provenance(self):
        result = build_synthesis_review(
            draft="Saved review draft.",
            claims=[{
                "text": "A claim with an exact quote.",
                "source_refs": ["s1"],
                "citations": [{
                    "source_id": "s1",
                    "excerpt": "source excerpt",
                }],
            }],
            source_registry=[{
                "source_id": "s1",
                "text": "Intro source excerpt ending.",
            }],
            decision="reject",
            reviewer="reviewer",
        )
        self.assertEqual(result["citation_audit"]["status"], "passed")
        self.assertEqual(result["citation_gate"]["claims_without_valid_citations"], 0)
        saved_citation = result["citation_audit"]["claims"][0]["citations"][0]
        self.assertEqual(saved_citation["excerpt"], "source excerpt")
        self.assertEqual(saved_citation["status"], "exact_excerpt_match")
        self.assertIn("does not establish semantic support", result["citation_gate"]["note"])


if __name__ == "__main__":
    unittest.main()
