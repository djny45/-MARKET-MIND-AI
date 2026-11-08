import unittest

from app.research_citation_audit import audit_claim_citations


class ResearchCitationAuditTests(unittest.TestCase):
    def test_exact_excerpt_matches_registry_source_text(self):
        result = audit_claim_citations(
            claims=[{
                "text": "A cited factual claim.",
                "citations": [{"source_id": "s1", "excerpt": "Exact source phrase."}],
            }],
            source_registry=[{
                "source_id": "s1", "title": "Fixture source",
                "url": "https://example.invalid/source",
                "text": "Context before. Exact source phrase. Context after.",
            }],
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["metrics"]["claim_citation_coverage"], 1.0)
        self.assertEqual(result["claims"][0]["citations"][0]["status"], "exact_excerpt_match")

    def test_unknown_source_and_nonmatching_excerpt_need_review(self):
        result = audit_claim_citations(
            claims=[{
                "text": "Claim.",
                "citations": [
                    {"source_id": "missing", "excerpt": "some quote"},
                    {"source_id": "s1", "excerpt": "not in the source"},
                ],
            }],
            source_registry=[{"source_id": "s1", "text": "actual source text"}],
        )
        self.assertEqual(result["status"], "needs_review")
        statuses = [item["status"] for item in result["claims"][0]["citations"]]
        self.assertEqual(statuses, ["unknown_source_id", "excerpt_not_found"])

    def test_source_text_missing_is_not_assumed_to_match(self):
        result = audit_claim_citations(
            claims=[{"text": "Claim.", "citations": [{"source_id": "s1", "excerpt": "quote"}]}],
            source_registry=[{"source_id": "s1", "title": "Metadata only"}],
        )
        self.assertEqual(result["claims"][0]["citations"][0]["status"], "source_text_unavailable")
        self.assertEqual(result["status"], "needs_review")

    def test_empty_claims_and_duplicate_source_ids_are_handled(self):
        result = audit_claim_citations(claims=[], source_registry=[])
        self.assertEqual(result["status"], "needs_review")
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_claim_citations(
                claims=[],
                source_registry=[{"source_id": "s1"}, {"source_id": "s1"}],
            )

    def test_rejects_invalid_claim_or_citation_bounds(self):
        with self.assertRaisesRegex(ValueError, "claim text"):
            audit_claim_citations(claims=[{"text": ""}], source_registry=[])
        with self.assertRaisesRegex(ValueError, "citations"):
            audit_claim_citations(
                claims=[{"text": "Claim", "citations": [{}] * 21}],
                source_registry=[],
            )


if __name__ == "__main__":
    unittest.main()
