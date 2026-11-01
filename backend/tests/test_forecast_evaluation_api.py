import unittest
from fastapi import HTTPException

from app.main import ForecastEvaluationRequest, evaluate_research_forecasts


def sample_records():
    base = "2026-02-01T00:00:00+00:00"
    return [
        {"partition": "holdout", "forecast_created_at": base,
         "origin_timestamp": base, "target_timestamp": f"2026-02-0{i+2}T00:00:00+00:00",
         "predicted_return": predicted, "actual_return": actual,
         "source_refs": [f"source:{i}"]}
        for i, (predicted, actual) in enumerate([(0.03, 0.02), (-0.01, -0.02), (0.0, 0.01)])
    ]


class ForecastEvaluationApiTests(unittest.TestCase):
    def test_endpoint_returns_holdout_metrics(self):
        result = evaluate_research_forecasts(ForecastEvaluationRequest(records=sample_records()))
        self.assertEqual(result["mode"], "heldout_forecast_error_evaluation")
        self.assertEqual(result["partition"], "holdout")
        self.assertEqual(result["observation_count"], 3)
        self.assertIn("mae_skill_vs_zero_return_baseline", result["metrics"])

    def test_endpoint_maps_leakage_failure_to_bad_request(self):
        rows = sample_records()
        rows[0]["forecast_created_at"] = "2026-02-03T00:00:00Z"
        with self.assertRaises(HTTPException) as error:
            evaluate_research_forecasts(ForecastEvaluationRequest(records=rows))
        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("after origin_timestamp", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
