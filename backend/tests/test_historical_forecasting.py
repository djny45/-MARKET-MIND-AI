"""Regression tests for historical forecasting evaluation.

All input prices are deterministic synthetic data. These tests validate
implementation mechanics, not predictive skill or market performance.
"""
import math
import unittest

from app.historical_forecasting import evaluate_next_day_return_forecast


class HistoricalForecastingTests(unittest.TestCase):
    @staticmethod
    def synthetic_closes(count=220):
        closes = [100.0]
        for i in range(count - 1):
            step = 0.0015 * math.sin(i * 0.37) + 0.0004 * math.cos(i * 0.11)
            closes.append(closes[-1] * math.exp(step))
        return closes

    def test_chronological_holdout_and_baseline_metrics(self):
        prices = self.synthetic_closes()
        report = evaluate_next_day_return_forecast(prices)

        self.assertTrue(report["research_only"])
        self.assertFalse(report["split"]["shuffle"])
        split = report["split"]
        self.assertEqual(
            split["train_samples"] + split["validation_samples"] + split["test_samples"],
            len(prices) - 1 - report["lookback"],
        )
        for key in ("test_model", "test_zero_return_baseline"):
            metrics = report[key]
            self.assertEqual(metrics["sample_count"], split["test_samples"])
            self.assertTrue(math.isfinite(metrics["mae_log_return"]))
            self.assertTrue(math.isfinite(metrics["rmse_log_return"]))
            self.assertTrue(0 <= metrics["directional_accuracy"] <= 1)

    def test_validation_alpha_candidates_and_selection(self):
        report = evaluate_next_day_return_forecast(self.synthetic_closes())
        candidates = {row["alpha"] for row in report["validation_mae_by_alpha"]}
        self.assertEqual(candidates, {1e-6, 1e-4, 1e-2, 1.0})
        self.assertIn(report["selected_ridge_alpha"], candidates)

    def test_rejects_invalid_prices(self):
        invalid_cases = (
            [100, 0, 101],
            [100, -1, 101],
            [100, float("nan"), 101],
            [100, float("inf"), 101],
            [100, True, 101],
        )
        for prices in invalid_cases:
            with self.subTest(prices=prices):
                with self.assertRaises(ValueError):
                    evaluate_next_day_return_forecast(prices)

    def test_rejects_invalid_lookback(self):
        for lookback in (True, 1, 21, 2.5, "5"):
            with self.subTest(lookback=lookback):
                with self.assertRaises(ValueError):
                    evaluate_next_day_return_forecast(
                        self.synthetic_closes(), lookback=lookback
                    )

    def test_rejects_insufficient_history(self):
        with self.assertRaisesRegex(ValueError, "insufficient history"):
            evaluate_next_day_return_forecast(self.synthetic_closes(50))


if __name__ == "__main__":
    unittest.main()
