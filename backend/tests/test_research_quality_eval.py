import unittest

from app.research_quality_eval import evaluate_research_draft


class ResearchQualityEvalTests(unittest.TestCase):
    def test_counts_claim_source_reference_coverage_and_unknown_ids(self):
        result = evaluate_research_draft(
            draft="Finding A. Limitations: source entailment not verified.",
            claims=[
                {"text": "Claim A", "source_refs": ["src-1"]},
                {"text": "Claim B", "source_refs": ["missing-src"]},
                {"text": "Claim C", "source_refs": []},
            ],
            source_registry=[{"source_id": "src-1", "title": "Provided source"}],
        )
        metrics = result["metrics"]
        self.assertAlmostEqual(metrics["claim_reference_coverage"], 2 / 3, places=4)
        self.assertAlmostEqual(metrics["known_source_reference_coverage"], 1 / 3, places=4)
        self.assertEqual(metrics["unknown_source_id_count"], 1)
        self.assertIn("limitation", metrics["uncertainty_markers"])
        self.assertEqual(result["evaluation_type"], "deterministic_research_traceability_check")

    def test_compares_metrics_with_explicit_baseline(self):
        result = evaluate_research_draft(
            draft="Draft with source refs.",
            claims=[{"text": "Claim", "source_refs": ["src"]}],
            source_registry=[{"source_id": "src"}],
            baseline={"metrics": {
                "claim_reference_coverage": 0.5,
                "known_source_reference_coverage": 0.5,
            }},
        )
        self.assertEqual(result["baseline_comparison"]["claim_reference_coverage"]["delta"], 0.5)

    def test_reports_duplicate_source_ids_after_normalization(self):
        result = evaluate_research_draft(
            draft="Duplicate registry IDs should be visible.",
            claims=[{"text": "Claim", "source_refs": ["src-1"]}],
            source_registry=[
                {"source_id": "src-1", "title": "First entry"},
                {"source_id": " src-1 ", "title": "Duplicate entry"},
                {"source_id": "src-2", "title": "Unique entry"},
            ],
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["source_registry_count"], 2)
        self.assertEqual(metrics["duplicate_source_id_count"], 1)
        self.assertEqual(metrics["duplicate_source_ids"], ["src-1"])

    def test_reports_source_registry_entries_without_ids(self):
        result = evaluate_research_draft(
            draft="Source registry includes an entry without an identifier.",
            claims=[{"text": "Claim", "source_refs": ["src-1"]}],
            source_registry=[
                {"source_id": "src-1", "title": "Identified source"},
                {"title": "Missing identifier"},
                {"source_id": "   ", "title": "Blank identifier"},
            ],
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["source_registry_count"], 1)
        self.assertEqual(metrics["source_registry_entries_without_id_count"], 2)
        self.assertEqual(metrics["known_source_reference_coverage"], 1.0)

    def test_reports_missing_source_provenance_fields(self):
        result = evaluate_research_draft(
            draft="Provenance completeness is a structural check only.",
            claims=[{"text": "Claim", "source_refs": ["src-a", "src-b"]}],
            source_registry=[
                {
                    "source_id": "src-a",
                    "title": "A title",
                    "url": "https://example.org/a",
                    "source_type": "paper",
                    "observed_at": "2026-11-07T12:00:00Z",
                },
                {
                    "source_id": "src-b",
                    "title": "B title",
                    "url": "https://example.org/b",
                    "source_type": "web",
                },
            ],
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["source_registry_entries_missing_provenance_count"], 1)
        self.assertEqual(metrics["source_registry_entries_complete_provenance_count"], 1)
        self.assertEqual(metrics["source_registry_provenance_completeness"], 0.5)
        self.assertEqual(
            metrics["source_registry_missing_provenance_by_field"],
            {"title": 0, "url": 0, "source_type": 0, "observed_at": 1},
        )
        self.assertIn("Provenance field presence is not source validation", result["interpretation"])
        self.assertEqual(metrics["claims_with_complete_source_provenance_refs"], 0)
        self.assertEqual(metrics["claims_with_incomplete_source_provenance_refs"], 1)
        self.assertEqual(metrics["incomplete_source_provenance_ids"], ["src-b"])
        self.assertEqual(
            result["claims"][0]["reference_status"],
            "registry_match_incomplete_provenance",
        )

    def test_duplicate_source_ids_are_provenance_incomplete_if_any_entry_is_incomplete(self):
        result = evaluate_research_draft(
            draft="Duplicate source identifiers are ambiguous.",
            claims=[{"text": "Claim", "source_refs": ["src-x"]}],
            source_registry=[
                {"source_id": "src-x", "title": "Complete", "url": "https://example.org/x",
                 "source_type": "paper", "observed_at": "2026-11-07"},
                {"source_id": "src-x", "title": "Incomplete"},
            ],
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["duplicate_source_id_count"], 1)
        self.assertEqual(metrics["claims_with_known_source_refs"], 1)
        self.assertEqual(metrics["claims_with_complete_source_provenance_refs"], 0)
        self.assertEqual(metrics["incomplete_source_provenance_ids"], ["src-x"])

    def test_flags_malformed_url_and_timestamp_without_claiming_source_validation(self):
        result = evaluate_research_draft(
            draft="URL and timestamp format checks are structural.",
            claims=[{"text": "Claim", "source_refs": ["bad-url", "bad-time", "good"]}],
            source_registry=[
                {"source_id": "bad-url", "title": "A", "url": "ftp://example.org/a",
                 "source_type": "paper", "observed_at": "2026-11-07T10:00:00Z"},
                {"source_id": "bad-time", "title": "B", "url": "https://example.org/b",
                 "source_type": "web", "observed_at": "yesterday"},
                {"source_id": "good", "title": "C", "url": "https://example.org/c",
                 "source_type": "web", "observed_at": "2026-11-07T10:00:00+00:00"},
            ],
        )
        metrics = result["metrics"]
        self.assertEqual(
            metrics["source_registry_invalid_provenance_by_field"],
            {"url": 1, "observed_at": 1},
        )
        self.assertEqual(
            metrics["incomplete_source_provenance_ids"],
            ["bad-time", "bad-url"],
        )
        self.assertIn("format only", result["interpretation"])

    def test_accepts_iso_timestamp_with_timezone_and_http_url(self):
        result = evaluate_research_draft(
            draft="Valid formats.",
            claims=[{"text": "Claim", "source_refs": ["src"]}],
            source_registry=[{
                "source_id": "src", "title": "Source",
                "url": "https://example.org/path",
                "source_type": "web", "observed_at": "2026-11-07T10:00:00+05:30",
            }],
        )
        self.assertEqual(result["metrics"]["claims_with_complete_source_provenance_refs"], 1)
        self.assertEqual(result["metrics"]["source_registry_entries_complete_provenance_count"], 1)
        self.assertEqual(result["metrics"]["source_registry_provenance_completeness"], 1.0)

    def test_empty_claim_set_has_null_coverage(self):
        result = evaluate_research_draft(draft="No claims.", claims=[], source_registry=[])
        self.assertIsNone(result["metrics"]["claim_reference_coverage"])

    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            evaluate_research_draft(draft="", claims=[], source_registry=[])
        with self.assertRaises(ValueError):
            evaluate_research_draft(
                draft="ok", claims=[{"text": "x", "source_refs": ["x"]}],
                source_registry=[], baseline={"wrong": "shape"},
            )


if __name__ == "__main__":
    unittest.main()
