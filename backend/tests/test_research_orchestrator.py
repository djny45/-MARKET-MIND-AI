import unittest

from app.research_orchestrator import build_research_brief


class ResearchOrchestratorTests(unittest.TestCase):
    def finding(self, market, value, quality="verified_by_importer"):
        return {
            "market_group": market, "topic": "volatility",
            "finding_key": "realized_volatility", "unit": "percent",
            "finding_value": value, "quality_status": quality,
            "worker_id": f"{market}-volatility",
            "source_refs": [f"historical-import:{market}"],
        }

    def test_aggregates_cross_market_findings_and_preserves_disagreement(self):
        result = build_research_brief([
            self.finding("india", 1.2), self.finding("us", 2.4),
        ], ["india", "us", "crypto"])
        self.assertEqual(result["findings_accepted"], 2)
        self.assertEqual(result["missing_market_groups"], ["crypto"])
        self.assertEqual(result["comparisons"][0]["distinct_value_count"], 2)
        self.assertEqual(result["comparisons"][0]["status"], "disagreement_requires_review")
        self.assertEqual(result["evidence_status"], "importer_verified")

    def test_synthetic_findings_never_count_as_verified(self):
        result = build_research_brief([self.finding("crypto", 5, "synthetic")], ["crypto"])
        self.assertEqual(result["verified_by_importer_findings"], 0)
        self.assertEqual(result["evidence_status"], "synthetic_only")

    def test_missing_market_is_not_reported_as_zero(self):
        result = build_research_brief([], ["india", "forex"])
        self.assertEqual(result["missing_market_groups"], ["india", "forex"])
        self.assertEqual(result["market_finding_counts"], {"india": 0, "forex": 0})
        self.assertEqual(result["evidence_status"], "no_findings")

    def test_rejects_invalid_quality_and_non_finite_values(self):
        with self.assertRaises(ValueError):
            build_research_brief([self.finding("india", 1, "trusted")])
        with self.assertRaises(ValueError):
            build_research_brief([self.finding("india", float("nan"))])

    def test_rejects_duplicate_or_unknown_requested_markets(self):
        with self.assertRaises(ValueError):
            build_research_brief([], ["india", "india"])
        with self.assertRaises(ValueError):
            build_research_brief([], ["global"])


if __name__ == "__main__":
    unittest.main()
