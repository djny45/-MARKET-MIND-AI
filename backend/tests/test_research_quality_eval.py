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

    def test_validates_optional_source_identity_metadata_and_reports_coverage(self):
        result = evaluate_research_draft(
            draft="A sourced draft.",
            claims=[{"text": "Claim", "source_refs": ["src-1"]}],
            source_registry=[
                {
                    "source_id": "src-1",
                    "title": "Example report",
                    "publisher": "Research publisher",
                    "url": "https://example.org/report",
                    "retrieved_at": "2026-11-12T08:00:00+00:00",
                    "content_sha256": "a" * 64,
                },
                {"source_id": "src-2", "title": "Metadata incomplete"},
            ],
        )
        self.assertEqual(result["metrics"]["sources_with_complete_identity_metadata"], 1)
        self.assertEqual(result["metrics"]["source_identity_metadata_coverage"], 0.5)

    def test_rejects_malformed_source_identity_metadata(self):
        invalid_sources = (
            {"source_id": "src", "url": "javascript:alert(1)"},
            {"source_id": "src", "url": "https:///missing-host"},
            {"source_id": "src", "retrieved_at": "2026-11-12T08:00:00"},
            {"source_id": "src", "content_sha256": "not-a-digest"},
            {"source_id": "src", "publisher": ""},
            {"source_id": "src", "title": "x" * 501},
        )
        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    evaluate_research_draft(
                        draft="Draft.",
                        claims=[],
                        source_registry=[source],
                    )

    def test_empty_source_registry_reports_unavailable_identity_coverage(self):
        result = evaluate_research_draft(draft="Draft.", claims=[], source_registry=[])
        self.assertIsNone(result["metrics"]["source_identity_metadata_coverage"])

    def test_reports_excerpts_only_when_they_match_registered_claim_references(self):
        result = evaluate_research_draft(
            draft="A draft with supplied excerpts.",
            claims=[
                {"text": "Claim A", "source_refs": ["src-1"],
                 "evidence": [{"source_id": "src-1", "excerpt": "Relevant supplied passage."}]},
                {"text": "Claim B", "source_refs": ["src-1"],
                 "evidence": [{"source_id": "unknown", "excerpt": "Unverified passage."}]},
                {"text": "Claim C", "source_refs": ["src-1"],
                 "evidence": [{"source_id": "src-2", "excerpt": "Orphaned passage."}]},
            ],
            source_registry=[{"source_id": "src-1"}, {"source_id": "src-2"}],
        )
        self.assertEqual(result["metrics"]["claims_with_provided_excerpts"], 1)
        self.assertAlmostEqual(result["metrics"]["claim_excerpt_coverage"], 1 / 3, places=4)
        self.assertEqual([c["evidence_status"] for c in result["claims"]],
                         ["provided_excerpt", "unknown_source_ids", "not_in_source_refs"])

    def test_rejects_malformed_claim_evidence(self):
        invalid_evidence = (
            "not-a-list",
            [{"source_id": "", "excerpt": "text"}],
            [{"source_id": "src", "excerpt": ""}],
            [{"source_id": "src", "excerpt": "x" * 2001}],
            [None],
        )
        for evidence in invalid_evidence:
            with self.subTest(evidence=evidence):
                with self.assertRaises(ValueError):
                    evaluate_research_draft(
                        draft="Draft.",
                        claims=[{"text": "Claim", "source_refs": ["src"], "evidence": evidence}],
                        source_registry=[{"source_id": "src"}],
                    )

    def test_rejects_missing_or_duplicate_source_ids(self):
        for registry in (
            [{"title": "Missing ID"}],
            [{"source_id": ""}],
            [{"source_id": "src"}, {"source_id": " src "}],
        ):
            with self.subTest(registry=registry):
                with self.assertRaisesRegex(ValueError, "source_id"):
                    evaluate_research_draft(
                        draft="Draft.",
                        claims=[{"text": "Claim", "source_refs": ["src"]}],
                        source_registry=registry,
                    )

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

    def test_baseline_summary_flags_lower_coverage_as_regression(self):
        result = evaluate_research_draft(
            draft="Draft.",
            claims=[{"text": "Claim 1", "source_refs": []},
                    {"text": "Claim 2", "source_refs": ["src"]}],
            source_registry=[{"source_id": "src"}],
            baseline={"metrics": {
                "claim_reference_coverage": 1.0,
                "known_source_reference_coverage": 1.0,
            }},
        )
        summary = result["baseline_comparison_summary"]
        self.assertEqual(summary["status"], "regression_detected")
        self.assertEqual(summary["regression_metrics"], [
            "claim_reference_coverage", "known_source_reference_coverage"
        ])
        self.assertEqual(summary["regression_metric_count"], 2)

    def test_complete_baseline_without_regression_is_comparison_complete(self):
        result = evaluate_research_draft(
            draft="Draft.",
            claims=[{"text": "Claim", "source_refs": ["src"]}],
            source_registry=[{"source_id": "src"}],
            baseline={"metrics": {
                "claim_reference_coverage": 0.5,
                "known_source_reference_coverage": 0.5,
            }},
        )
        summary = result["baseline_comparison_summary"]
        self.assertEqual(summary["status"], "comparison_complete")
        self.assertEqual(summary["regression_metric_count"], 0)
        self.assertEqual(summary["regression_metrics"], [])

    def test_rejects_invalid_baseline_metric_values(self):
        for value in (-0.01, 1.01, True, "0.8"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    evaluate_research_draft(
                        draft="Draft.",
                        claims=[{"text": "Claim", "source_refs": ["s1"]}],
                        source_registry=[{"source_id": "s1"}],
                        baseline={"metrics": {"claim_reference_coverage": value}},
                    )

    def test_rejects_baseline_without_supported_metrics(self):
        with self.assertRaises(ValueError):
            evaluate_research_draft(
                draft="Draft.", claims=[], source_registry=[],
                baseline={"metrics": {"factual_accuracy": 0.9}},
            )

    def test_rejects_unknown_metric_even_when_supported_metric_is_present(self):
        with self.assertRaises(ValueError):
            evaluate_research_draft(
                draft="Draft.", claims=[], source_registry=[],
                baseline={"metrics": {
                    "claim_reference_coverage": 0.8,
                    "claim_referance_coverage": 0.7,
                }},
            )

    def test_missing_baseline_metric_is_reported_as_incomplete(self):
        result = evaluate_research_draft(
            draft="Draft.", claims=[{"text": "Claim", "source_refs": ["src"]}],
            source_registry=[{"source_id": "src"}],
            baseline={"metrics": {"claim_reference_coverage": 0.5}},
        )
        comparison = result["baseline_comparison"]["known_source_reference_coverage"]
        self.assertEqual(comparison["status"], "skipped")
        self.assertEqual(comparison["reason"], "baseline_metric_missing")
        self.assertEqual(
            result["baseline_comparison_summary"]["status"],
            "comparison_incomplete",
        )
        self.assertEqual(
            result["baseline_comparison_summary"]["skipped_comparison_count"], 1
        )

    def test_empty_claim_set_reports_unavailable_comparisons(self):
        result = evaluate_research_draft(
            draft="No claims.", claims=[], source_registry=[],
            baseline={"metrics": {
                "claim_reference_coverage": 0.8,
                "known_source_reference_coverage": 0.7,
            }},
        )
        self.assertEqual(
            result["baseline_comparison_summary"]["status"],
            "comparison_incomplete",
        )
        self.assertEqual(
            result["baseline_comparison_summary"]["skipped_comparison_count"], 2
        )

    def test_empty_claim_set_has_null_coverage(self):
        result = evaluate_research_draft(draft="No claims.", claims=[], source_registry=[])
        self.assertIsNone(result["metrics"]["claim_reference_coverage"])

    def test_validates_baseline_before_draft(self):
        with self.assertRaisesRegex(ValueError, "unsupported metrics"):
            evaluate_research_draft(
                draft="", claims=[], source_registry=[],
                baseline={"metrics": {"unknown_metric": 0.8}},
            )

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
