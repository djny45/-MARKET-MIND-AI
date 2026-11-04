import unittest
from app.research_export import build_research_evidence_bundle, render_research_methodology_markdown

class ResearchMethodologyMarkdownTests(unittest.TestCase):
    def test_report_contains_source_provenance_digest_and_scope(self):
        bundle = build_research_evidence_bundle("btcusd", "1h", {
            "bars": [], "source": "fixture", "sources": ["fixture"],
            "status": "synthetic", "retrieved_at": "2026-01-02T00:00:00Z"})
        report = render_research_methodology_markdown(bundle)
        self.assertIn("# Historical Research Report: BTCUSD", report)
        self.assertIn("fixture", report)
        self.assertIn(bundle["integrity"]["digest"], report)
        self.assertIn("not a forecast", report.lower())

    def test_rejects_wrong_bundle_type(self):
        with self.assertRaises(ValueError):
            render_research_methodology_markdown({"report_type": "other"})

if __name__ == "__main__":
    unittest.main()
