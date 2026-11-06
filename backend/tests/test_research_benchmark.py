import unittest

from app.research_benchmark import run_offline_research_benchmark


def fixture_cases():
    return [
        {
            "case_id": "synthetic-complete",
            "draft": "Synthetic example with an explicit limitation.",
            "claims": [{"text": "Fixture claim A", "source_refs": ["fixture-source"]}],
            "source_registry": [{"source_id": "fixture-source"}],
        },
        {
            "case_id": "synthetic-missing-reference",
            "draft": "Synthetic example; source not verified.",
            "claims": [{"text": "Fixture claim B", "source_refs": ["unknown-source"]}],
            "source_registry": [{"source_id": "fixture-source"}],
        },
    ]


class ResearchBenchmarkTests(unittest.TestCase):
    def test_benchmark_is_deterministic_and_aggregates_metrics(self):
        first = run_offline_research_benchmark(fixture_cases())
        second = run_offline_research_benchmark(fixture_cases())
        self.assertEqual(first["benchmark_id"], second["benchmark_id"])
        self.assertEqual(first["aggregate_metrics"]["claim_reference_coverage"]["mean"], 1.0)
        self.assertEqual(first["aggregate_metrics"]["known_source_reference_coverage"]["mean"], 0.5)
        self.assertEqual(first["case_count"], 2)
        self.assertEqual(first["benchmark_type"], "offline_research_traceability")

    def test_changed_fixture_changes_benchmark_id_and_baseline_delta(self):
        baseline = run_offline_research_benchmark(fixture_cases())
        cases = fixture_cases()
        cases[1]["claims"] = [{"text": "Fixture claim B", "source_refs": ["fixture-source"]}]
        current = run_offline_research_benchmark(
            cases, baseline={"metrics": baseline["aggregate_metrics"] and {
                key: value["mean"] for key, value in baseline["aggregate_metrics"].items()
            }},
        )
        self.assertNotEqual(baseline["benchmark_id"], current["benchmark_id"])
        self.assertEqual(
            current["baseline_comparison"]["known_source_reference_coverage"]["delta"],
            0.5,
        )


    def test_flags_traceability_regression_at_threshold(self):
        baseline = run_offline_research_benchmark(fixture_cases())
        cases = fixture_cases()
        cases[0]["claims"] = [{"text": "Claim A", "source_refs": ["missing"]}]
        cases[1]["claims"] = [{"text": "Claim B", "source_refs": ["missing"]}]
        current = run_offline_research_benchmark(
            cases,
            baseline={"metrics": {
                key: value["mean"]
                for key, value in baseline["aggregate_metrics"].items()
            }},
            regression_threshold=0.05,
        )
        self.assertEqual(
            current["regression_summary"]["status"], "regression_detected"
        )
        self.assertEqual(
            current["regression_summary"]["items"][0]["metric"],
            "known_source_reference_coverage",
        )


    def test_rejects_invalid_baseline_metric_values(self):
        invalid_values = (-0.1, 1.1, True, "0.8")
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    run_offline_research_benchmark(
                        fixture_cases(),
                        baseline={"metrics": {"claim_reference_coverage": value}},
                    )

    def test_rejects_baseline_without_supported_metrics(self):
        with self.assertRaises(ValueError):
            run_offline_research_benchmark(
                fixture_cases(), baseline={"metrics": {"other_metric": 0.8}}
            )

    def test_rejects_invalid_regression_threshold(self):
        for threshold in (-0.1, 1.1, True, "0.05"):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    run_offline_research_benchmark(
                        fixture_cases(), regression_threshold=threshold
                    )

    def test_rejects_empty_oversized_and_duplicate_case_sets(self):
        with self.assertRaises(ValueError):
            run_offline_research_benchmark([])
        with self.assertRaises(ValueError):
            run_offline_research_benchmark(fixture_cases() * 51)
        duplicate = fixture_cases()
        duplicate[1]["case_id"] = duplicate[0]["case_id"]
        with self.assertRaises(ValueError):
            run_offline_research_benchmark(duplicate)

    def test_rejects_invalid_baseline_shape(self):
        with self.assertRaises(ValueError):
            run_offline_research_benchmark(fixture_cases(), baseline={"bad": "shape"})


if __name__ == "__main__":
    unittest.main()
