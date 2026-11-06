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
        fence = chr(96) * 3
        self.assertIn("## Data-quality diagnostics\n" + fence + "json\n", report)
        self.assertIn("## Source comparison\n" + fence + "json\n", report)
        self.assertIn("## Descriptive timeline\n" + fence + "json\n", report)
        self.assertEqual(report.count(fence + "json"), 3)
        self.assertEqual(report.count(fence), 6)

    def test_untrusted_metadata_cannot_inject_markdown_structure(self):
        bundle = build_research_evidence_bundle("BTC\n## injected", "1h|[click](https://bad.example)", {
            "bars": [], "source": "fixture\n- injected item", "sources": ["fixture\n## forged heading"],
            "status": "synthetic", "retrieved_at": "2026-01-02T00:00:00Z"})
        report = render_research_methodology_markdown(bundle)
        self.assertIn(r"BTC \#\# INJECTED", report)
        self.assertIn("1h\\|\\[click\\]", report)
        self.assertIn(r"fixture \#\# forged heading", report)
        self.assertNotIn("\n## injected", report)
        self.assertNotIn("\n## forged heading", report)

    def test_json_code_fence_cannot_be_closed_by_source_metadata(self):
        timestamp = "2026-01-02T00:00:00Z"
        bundle = build_research_evidence_bundle("BTCUSD", "1h", {
            "bars": [
                {"timestamp": timestamp, "source": "feed-a", "open": 1, "high": 2, "low": 1, "close": 1, "volume": 10},
                {"timestamp": timestamp, "source": "feed-```\n## injected heading", "open": 1, "high": 2, "low": 1, "close": 1, "volume": 10},
            ]
        })
        report = render_research_methodology_markdown(bundle)
        self.assertIn("````json\n", report)
        self.assertIn("\n````\n", report)
        source_section = report.split("## Source comparison\n", 1)[1]
        source_section = source_section.split("\n## Integrity\n", 1)[0]
        self.assertNotIn("\n```\n", source_section)
        self.assertIn("feed-```", report)


    def test_invalid_ohlcv_is_retained_with_timeline_validation_error(self):
        bundle = build_research_evidence_bundle("BTCUSD", "1h", {
            "bars": [{"open": 10, "high": 9, "low": 8, "close": 10, "volume": 1}],
        })
        self.assertEqual(bundle["observations"][0]["high"], 9)
        self.assertEqual(bundle["timeline"]["status"], "unavailable_invalid_ohlcv")
        self.assertIn("high must be >= open and close", bundle["timeline"]["validation_error"])

    def test_malformed_optional_scope_integrity_and_source_metadata_are_safe(self):
        bundle = build_research_evidence_bundle("BTCUSD", "1h", {
            "bars": [], "source": "fallback-source"
        })
        bundle["scope"] = ["malformed", "scope"]
        bundle["integrity"] = ["malformed", "integrity"]
        report = render_research_methodology_markdown(bundle)
        self.assertIn("- **Symbol:** Not supplied", report)
        self.assertIn("- **Source metadata:** fallback-source", report)
        self.assertIn("- **Algorithm:** Not supplied", report)
        self.assertIn("- **Digest:** Not supplied", report)

    def test_rejects_wrong_bundle_type(self):
        with self.assertRaises(ValueError):
            render_research_methodology_markdown({"report_type": "other"})


if __name__ == "__main__":
    unittest.main()
