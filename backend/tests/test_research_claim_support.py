import unittest

from app.research_claim_support import audit_claim_source_overlap


class ResearchClaimSupportTests(unittest.TestCase):
    def test_reports_overlap_without_claiming_semantic_support(self):
        result = audit_claim_source_overlap(
            claims=[{
                "text": "Solar energy output increased in 2024.",
                "source_refs": ["s1"],
            }],
            source_registry=[{
                "source_id": "s1",
                "text": "Solar energy output increased during 2024.",
            }],
        )
        item = result["claims"][0]["sources"][0]
        self.assertEqual(result["status"], "screened_not_semantically_verified")
        self.assertEqual(item["status"], "lexical_overlap_screened")
        self.assertGreater(item["overlap_score"], 0)
        self.assertEqual(result["claims"][0]["status"], "needs_human_semantic_review")

    def test_unknown_source_and_missing_text_are_not_scored(self):
        result = audit_claim_source_overlap(
            claims=[{
                "text": "Claim with source references.",
                "source_refs": ["unknown", "metadata-only"],
            }],
            source_registry=[{"source_id": "metadata-only", "title": "No source body"}],
        )
        statuses = [source["status"] for source in result["claims"][0]["sources"]]
        self.assertEqual(statuses, ["unknown_source_id", "source_text_unavailable"])
        self.assertTrue(all(source["overlap_score"] is None
                            for source in result["claims"][0]["sources"]))

    def test_no_refs_and_empty_claim_list_are_safe(self):
        result = audit_claim_source_overlap(
            claims=[{"text": "Unreferenced claim.", "source_refs": []}],
            source_registry=[],
        )
        self.assertEqual(result["claims"][0]["source_count"], 0)
        empty = audit_claim_source_overlap(claims=[], source_registry=[])
        self.assertEqual(empty["claims"], [])

    def test_duplicate_source_ids_and_bounds_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_claim_source_overlap(
                claims=[], source_registry=[
                    {"source_id": "s1"}, {"source_id": "s1"},
                ],
            )
        with self.assertRaisesRegex(ValueError, "claim text"):
            audit_claim_source_overlap(
                claims=[{"text": ""}], source_registry=[],
            )


if __name__ == "__main__":
    unittest.main()
