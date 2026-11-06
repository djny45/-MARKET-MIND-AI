import unittest

from app.main import ResearchQualityEvaluationRequest, evaluate_research_quality


class ResearchQualityApiTests(unittest.TestCase):
    def test_endpoint_returns_traceability_metrics(self):
        request = ResearchQualityEvaluationRequest(
            draft="Some claim; limitation: source meaning is not verified.",
            claims=[{"text": "Example claim", "source_refs": ["ref-a"]}],
            source_registry=[{"source_id": "ref-a"}],
        )
        result = evaluate_research_quality(request)
        self.assertEqual(result["evaluation_type"], "deterministic_research_traceability_check")
        self.assertEqual(result["metrics"]["known_source_reference_coverage"], 1.0)

    def test_endpoint_translates_invalid_evaluation_to_http_400(self):
        request = ResearchQualityEvaluationRequest(
            draft="   ",
            claims=[],
            source_registry=[],
        )
        with self.assertRaises(Exception) as raised:
            evaluate_research_quality(request)
        self.assertEqual(getattr(raised.exception, "status_code", None), 400)


    def test_task_quality_endpoint_returns_not_evaluated_for_valid_task(self):
        import os
        import tempfile
        from unittest.mock import patch
        from app.analytical_agent_tasks import enqueue_research_task
        from app.main import analytical_agent_task_quality_evaluation
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(temp, "quality.sqlite")}):
                queued = enqueue_research_task("worker_018", "No quality eval")
                result = analytical_agent_task_quality_evaluation(queued["task_id"])
                self.assertEqual(result["status"], "not_evaluated")
                self.assertEqual(result["task_id"], queued["task_id"])

    def test_task_quality_endpoint_returns_404_for_unknown_task(self):
        from fastapi import HTTPException
        from app.main import analytical_agent_task_quality_evaluation
        with self.assertRaises(HTTPException) as raised:
            analytical_agent_task_quality_evaluation("missing-task")
        self.assertEqual(raised.exception.status_code, 404)


    def test_offline_benchmark_api_returns_deterministic_metrics(self):
        from app.main import ResearchBenchmarkRequest, run_research_benchmark
        request = ResearchBenchmarkRequest(cases=[{
            "case_id": "api-fixture",
            "draft": "Synthetic fixture; limitation noted.",
            "claims": [{"text": "Fixture claim", "source_refs": ["fixture-ref"]}],
            "source_registry": [{"source_id": "fixture-ref"}],
        }])
        first = run_research_benchmark(request)
        second = run_research_benchmark(request)
        self.assertEqual(first["benchmark_id"], second["benchmark_id"])
        self.assertEqual(first["aggregate_metrics"]["known_source_reference_coverage"]["mean"], 1.0)
        self.assertIn("does not fetch live data", first["limitations"][0])


    def test_benchmark_api_reports_baseline_regression(self):
        from app.main import ResearchBenchmarkRequest, run_research_benchmark
        cases = [{
            "case_id": "regression-fixture",
            "draft": "Synthetic fixture with a source reference.",
            "claims": [{"text": "Fixture claim", "source_refs": ["unknown-ref"]}],
            "source_registry": [{"source_id": "known-ref"}],
        }]
        request = ResearchBenchmarkRequest(
            cases=cases,
            baseline={"metrics": {
                "claim_reference_coverage": 1.0,
                "known_source_reference_coverage": 1.0,
            }},
            regression_threshold=0.05,
        )
        result = run_research_benchmark(request)
        self.assertEqual(result["regression_summary"]["status"], "regression_detected")
        self.assertEqual(
            result["regression_summary"]["items"][0]["metric"],
            "known_source_reference_coverage",
        )
        self.assertAlmostEqual(
            result["regression_summary"]["items"][0]["delta"], -1.0
        )

    def test_benchmark_api_rejects_out_of_range_regression_threshold(self):
        from pydantic import ValidationError
        from app.main import ResearchBenchmarkRequest
        with self.assertRaises(ValidationError):
            ResearchBenchmarkRequest(cases=[{"case_id": "x"}], regression_threshold=1.5)


    def test_benchmark_api_exposes_baseline_regression_summary(self):
        from app.main import ResearchBenchmarkRequest, run_research_benchmark
        baseline = {"metrics": {
            "claim_reference_coverage": 1.0,
            "known_source_reference_coverage": 1.0,
        }}
        request = ResearchBenchmarkRequest(
            cases=[{
                "case_id": "baseline-regression-fixture",
                "draft": "Fixture only; source structure is evaluated.",
                "claims": [{"text": "Claim", "source_refs": ["missing-ref"]}],
                "source_registry": [{"source_id": "known-ref"}],
            }],
            baseline=baseline,
            regression_threshold=0.05,
        )
        result = run_research_benchmark(request)
        self.assertEqual(result["regression_summary"]["status"], "regression_detected")
        self.assertEqual(result["regression_summary"]["threshold"], 0.05)
        self.assertTrue(result["regression_summary"]["items"])

    def test_benchmark_api_rejects_threshold_outside_range(self):
        from pydantic import ValidationError
        from app.main import ResearchBenchmarkRequest
        for threshold in (-0.01, 1.01):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValidationError):
                    ResearchBenchmarkRequest(
                        cases=[{"case_id": "fixture", "draft": "x", "claims": [], "source_registry": []}],
                        regression_threshold=threshold,
                    )

    def test_offline_benchmark_api_translates_invalid_case_to_400(self):
        from fastapi import HTTPException
        from app.main import ResearchBenchmarkRequest, run_research_benchmark
        request = ResearchBenchmarkRequest(cases=[{
            "case_id": "bad-fixture", "draft": "", "claims": [], "source_registry": [],
        }])
        with self.assertRaises(HTTPException) as raised:
            run_research_benchmark(request)
        self.assertEqual(raised.exception.status_code, 400)

if __name__ == "__main__":
    unittest.main()
