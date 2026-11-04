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

    def test_empty_optional_metadata_uses_not_supplied_fallback(self):
        bundle = build_research_evidence_bundle("btcusd", "1h", {
            "bars": [], "status": None, "retrieved_at": None})
        report = render_research_methodology_markdown(bundle)
        self.assertIn("- **Status:** Not supplied", report)
        self.assertNotIn("- **Status:** None", report)

    def test_json_diagnostics_are_rendered_as_fenced_blocks(self):
        bundle = build_research_evidence_bundle("btcusd", "1h", {"bars": []})
        report = render_research_methodology_markdown(bundle)
        self.assertIn("## Data-quality diagnostics\\n\`\`\`json\\n", report)
        self.assertIn("## Source comparison\\n\`\`\`json\\n", report)
        self.assertEqual(report.count("\`\`\`json"), 2)
        self.assertEqual(report.count("\`\`\`"), 4)

    def test_untrusted_metadata_cannot_inject_markdown_structure(self):
        bundle = build_research_evidence_bundle("BTC\\n## injected", "1h|[click](https://bad.example)", {
            "bars": [], "source": "fixture\\n- injected item", "sources": ["fixture\\n## forged heading"],
            "status": "synthetic", "retrieved_at": "2026-01-02T00:00:00Z"})
        report = render_research_methodology_markdown(bundle)
        self.assertIn(r"BTC \\#\\# injected", report)
        self.assertIn("1h\\\\|\\\\[click\\\\]", report)
        self.assertIn(r"fixture \\#\\# forged heading", report)
        self.assertNotIn("\\n## injected", report)
        self.assertNotIn("\\n## forged heading", report)

    def test_rejects_wrong_bundle_type(self):
        with self.assertRaises(ValueError):
            render_research_methodology_markdown({"report_type": "other"})


if __name__ == "__main__":
    unittest.main()
