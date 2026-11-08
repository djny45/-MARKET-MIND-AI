import unittest

from app.research_evidence_audit import audit_evidence


class EvidenceAuditTests(unittest.TestCase):
    def test_duplicate_urls_are_grouped_and_not_counted_as_independent_sources(self):
        result = audit_evidence(
            claims=[{"text": "Claim", "source_refs": ["a", "b"]}],
            source_registry=[
                {"source_id": "a", "url": "https://example.org/story#top"},
                {"source_id": "b", "url": "https://EXAMPLE.org/story/"},
            ],
        )
        self.assertEqual(result["metrics"]["source_group_count"], 1)
        self.assertEqual(result["metrics"]["duplicate_or_shared_source_group_count"], 1)
        self.assertEqual(result["claims"][0]["source_group_count"], 1)

    def test_explicit_opposing_stances_with_distinct_source_groups_are_review_candidates(self):
        result = audit_evidence(
            claims=[
                {"text": "Claim appears true", "claim_key": "claim-1",
                 "stance": "supports", "source_refs": ["src-a"]},
                {"text": "Claim appears false", "claim_key": "claim-1",
                 "stance": "contradicts", "source_refs": ["src-b"]},
            ],
            source_registry=[
                {"source_id": "src-a", "url": "https://a.example/report"},
                {"source_id": "src-b", "url": "https://b.example/report"},
            ],
        )
        self.assertEqual(result["metrics"]["claim_disagreement_candidate_count"], 1)
        candidate = result["disagreement_candidates"][0]
        self.assertEqual(candidate["status"], "human_review_required")
        self.assertEqual(candidate["claim_key"], "claim-1")

    def test_same_source_group_does_not_create_independent_disagreement_candidate(self):
        result = audit_evidence(
            claims=[
                {"text": "Support", "claim_key": "k", "stance": "supports",
                 "source_refs": ["s1"]},
                {"text": "Contradiction", "claim_key": "k", "stance": "contradicts",
                 "source_refs": ["s2"]},
            ],
            source_registry=[
                {"source_id": "s1", "independence_group": "publisher-story"},
                {"source_id": "s2", "independence_group": "publisher-story"},
            ],
        )
        self.assertEqual(result["disagreement_candidates"], [])

    def test_unknown_source_ids_are_reported_not_silently_accepted(self):
        result = audit_evidence(
            claims=[{"text": "Claim", "source_refs": ["not-in-registry"]}],
            source_registry=[],
        )
        self.assertEqual(result["metrics"]["unknown_source_id_count"], 1)
        self.assertEqual(result["claims"][0]["reference_status"], "unknown_ids")

    def test_rejects_duplicate_source_ids_and_invalid_stance(self):
        with self.assertRaises(ValueError):
            audit_evidence(
                claims=[],
                source_registry=[{"source_id": "x"}, {"source_id": "x"}],
            )
        with self.assertRaises(ValueError):
            audit_evidence(
                claims=[{"text": "Claim", "claim_key": "k", "stance": "maybe"}],
                source_registry=[],
            )

    def test_missing_claims_return_unavailable_coverage(self):
        result = audit_evidence(claims=[], source_registry=[])
        self.assertIsNone(result["metrics"]["claim_reference_coverage"])
        self.assertEqual(result["metrics"]["claim_disagreement_candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
