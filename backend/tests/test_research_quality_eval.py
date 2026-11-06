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
