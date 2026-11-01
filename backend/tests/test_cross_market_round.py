import unittest

from app.cross_market_round import build_research_round


class CrossMarketRoundTests(unittest.TestCase):
    def test_round_passes_when_each_requested_market_has_source_reference(self):
        messages = [
            {"market_group": "india", "agent_id": "in-1", "topic": "macro",
             "quality_status": "verified_by_importer", "source_refs": ["src:in"],
             "payload": {"finding_key": "risk", "finding_value": "high"}},
            {"market_group": "us", "agent_id": "us-1", "topic": "macro",
             "quality_status": "partial", "source_refs": ["src:us"],
             "payload": {"finding_key": "risk", "finding_value": "moderate"}},
        ]
        result = build_research_round(messages, ["india", "us"])
        self.assertEqual(result["status"], "ready_for_human_review")
        self.assertTrue(result["review_gate"]["passed"])
        self.assertEqual(result["represented_market_groups"], ["india", "us"])

    def test_round_blocks_market_without_provenance(self):
        messages = [
            {"market_group": "india", "agent_id": "in-1", "topic": "macro",
             "quality_status": "unverified", "source_refs": [],
             "payload": {"finding_key": "risk", "finding_value": "high"}},
        ]
        result = build_research_round(messages, ["india", "us"])
        self.assertEqual(result["status"], "incomplete_evidence")
        self.assertEqual(result["insufficient_provenance_markets"], ["india", "us"])

    def test_duplicate_source_refs_count_once(self):
        messages = [
            {"market_group": "crypto", "source_refs": ["src:a", "src:a"],
             "quality_status": "synthetic", "payload": {}},
        ]
        result = build_research_round(messages, ["crypto"])
        self.assertEqual(result["source_coverage"][0]["distinct_source_ref_count"], 1)

    def test_rejects_invalid_market_selection_and_threshold(self):
        with self.assertRaises(ValueError):
            build_research_round([], ["global"])
        with self.assertRaises(ValueError):
            build_research_round([], ["india"], 0)


if __name__ == "__main__":
    unittest.main()
