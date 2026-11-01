import unittest
from app.forecast_evaluation import evaluate_heldout_forecasts


def records():
    base = "2026-01-01T00:00:00+00:00"
    return [
        {"partition": "holdout", "forecast_created_at": base,
         "origin_timestamp": base, "target_timestamp": f"2026-01-0{i+2}T00:00:00+00:00",
         "predicted_return": p, "actual_return": a, "source_refs": [f"fixture:{i}"]}
        for i, (p, a) in enumerate([(0.02, 0.01), (-0.01, -0.02), (0.0, 0.01)])
    ]


class HeldoutForecastEvaluationTests(unittest.TestCase):
    def test_metrics_and_baseline_are_reported(self):
        result = evaluate_heldout_forecasts(records())
        self.assertEqual(result["observation_count"], 3)
        self.assertAlmostEqual(result["metrics"]["mae"], 0.01)
        self.assertAlmostEqual(result["metrics"]["zero_return_baseline_mae"], 0.013333333333333334)
        self.assertEqual(result["metrics"]["directional_accuracy"], 1.0)
        self.assertTrue(result["leakage_checks"]["all_forecasts_created_at_or_before_origin"])

    def test_forecast_created_after_origin_is_rejected(self):
        rows = records()
        rows[0]["forecast_created_at"] = "2026-01-02T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "after origin_timestamp"):
            evaluate_heldout_forecasts(rows)

    def test_target_must_be_after_origin(self):
        rows = records()
        rows[0]["target_timestamp"] = rows[0]["origin_timestamp"]
        with self.assertRaisesRegex(ValueError, "must be after origin_timestamp"):
            evaluate_heldout_forecasts(rows)

    def test_only_holdout_partition_is_accepted(self):
        rows = records()
        rows[1]["partition"] = "validation"
        with self.assertRaisesRegex(ValueError, "holdout partition"):
            evaluate_heldout_forecasts(rows)

    def test_duplicate_origin_target_pair_is_rejected(self):
        rows = records()
        rows[1]["origin_timestamp"] = rows[0]["origin_timestamp"]
        rows[1]["target_timestamp"] = rows[0]["target_timestamp"]
        with self.assertRaisesRegex(ValueError, "duplicates an origin/target pair"):
            evaluate_heldout_forecasts(rows)

    def test_nonfinite_values_and_missing_provenance_are_rejected(self):
        rows = records()
        rows[0]["predicted_return"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite number"):
            evaluate_heldout_forecasts(rows)
        rows = records()
        rows[0]["source_refs"] = []
        with self.assertRaisesRegex(ValueError, "source_refs"):
            evaluate_heldout_forecasts(rows)

    def test_naive_timestamp_is_rejected(self):
        rows = records()
        rows[0]["origin_timestamp"] = "2026-01-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "include a timezone"):
            evaluate_heldout_forecasts(rows)

    def test_input_size_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "between 3 and 10000"):
            evaluate_heldout_forecasts([])


if __name__ == "__main__":
    unittest.main()
