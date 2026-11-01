import unittest
from app.worker_evaluation import evaluate_worker_capabilities


class WorkerEvaluationTests(unittest.TestCase):
    def test_all_mapped_operations_pass_fixed_smoke_evaluation(self):
        report = evaluate_worker_capabilities()
        self.assertEqual(report["status"], "passed")
        self.assertGreater(report["mapped_operation_count"], 0)
        self.assertEqual(report["passed_operations"], report["mapped_operation_count"])
        self.assertEqual(report["failed_operations"], 0)
        self.assertEqual(report["evaluation_mode"], "fixed_synthetic_smoke_test")
        self.assertTrue(report["research_only"])

    def test_evaluation_covers_all_currently_mapped_operation_types(self):
        report = evaluate_worker_capabilities()
        operations = {item["operation"] for item in report["evaluations"]}
        self.assertEqual(
            operations,
            {"sma", "ema", "rsi", "macd", "bollinger", "returns",
             "volatility", "data_quality", "research_summary"},
        )

    def test_report_does_not_claim_live_or_predictive_validation(self):
        report = evaluate_worker_capabilities()
        self.assertIn(
            "This checks deterministic wiring and output shape, not analytical correctness or predictive performance.",
            report["limitations"],
        )


if __name__ == "__main__":
    unittest.main()
