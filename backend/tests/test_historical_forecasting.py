"""Regression tests for historical forecasting evaluation.

All input prices are deterministic synthetic data. These tests validate
implementation mechanics, not predictive skill or market performance.
"""
import math
import unittest

from app.historical_forecasting import evaluate_next_day_return_forecast, evaluate_walk_forward_forecast


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

    def test_holdout_comparison_reports_error_reduction_without_claiming_edge(self):
        report = evaluate_next_day_return_forecast(self.synthetic_closes())
        comparison = report["test_vs_zero_return_baseline"]
        model = report["test_model"]
        baseline = report["test_zero_return_baseline"]

        for metric in ("mae", "rmse"):
            values = comparison[metric]
            model_key = "mae_log_return" if metric == "mae" else "rmse_log_return"
            expected = baseline[model_key] - model[model_key]
            self.assertAlmostEqual(values["absolute_error_reduction"], expected)
            if baseline[model_key] > 0:
                self.assertAlmostEqual(
                    values["relative_error_reduction"],
                    expected / baseline[model_key],
                )
        self.assertIn("not evidence of tradable edge", comparison["interpretation"])

    def test_pretest_mean_baseline_is_reported_and_fit_before_test(self):
        report = evaluate_next_day_return_forecast(self.synthetic_closes())
        baseline = report["pretest_mean_return_baseline"]
        split = report["split"]
        self.assertEqual(baseline["fit_samples"], split["train_samples"] + split["validation_samples"])
        self.assertEqual(baseline["sample_count"], split["test_samples"])
        self.assertTrue(math.isfinite(baseline["forecast_log_return"]))
        self.assertIn("test_vs_pretest_mean_baseline", report)
        for metric in ("mae", "rmse"):
            self.assertIn("absolute_error_reduction", report["test_vs_pretest_mean_baseline"][metric])

    def test_validation_alpha_candidates_and_selection(self):
        report = evaluate_next_day_return_forecast(self.synthetic_closes())
        candidates = {row["alpha"] for row in report["validation_mae_by_alpha"]}
        self.assertEqual(candidates, {1e-6, 1e-4, 1e-2, 1.0})
        self.assertIn(report["selected_ridge_alpha"], candidates)

    def test_log_returns_avoid_intermediate_ratio_overflow(self):
        from app.historical_forecasting import _log_returns

        values = _log_returns([1e-300, 1e300, 1e-300])
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertAlmostEqual(values[0], math.log(1e300) - math.log(1e-300))
        self.assertAlmostEqual(values[1], math.log(1e-300) - math.log(1e300))

    def test_rejects_integer_too_large_for_float_conversion(self):
        from app.historical_forecasting import _log_returns

        with self.assertRaisesRegex(ValueError, r"prices\[0\] must be finite and positive"):
            _log_returns([10**10000, 100.0])

    def test_metrics_reject_empty_mismatched_and_nonfinite_inputs(self):
        from app.historical_forecasting import _metrics

        for actual, predicted, message in (
            ([], [], "non-empty"),
            ([0.1], [], "equal lengths"),
            ([0.1], [float("nan")], r"predicted\[0\] must be finite"),
            ([float("inf")], [0.1], r"actual\[0\] must be finite"),
            ([True], [0.1], r"actual\[0\] must be numeric"),
        ):
            with self.subTest(actual=actual, predicted=predicted):
                with self.assertRaisesRegex(ValueError, message):
                    _metrics(actual, predicted)

    def test_metrics_reject_nonfinite_error_overflow(self):
        from app.historical_forecasting import _metrics

        with self.assertRaisesRegex(ValueError, "forecast errors must be finite"):
            _metrics([-1e308], [1e308])

    def test_metrics_normalize_integer_error_float_conversion_overflow(self):
        from app.historical_forecasting import _metrics

        with self.assertRaisesRegex(ValueError, "forecast errors must be finite"):
            _metrics([-(10**308)], [10**308])

    def test_metrics_rmse_handles_large_finite_errors_without_square_overflow(self):
        from app.historical_forecasting import _metrics

        metrics = _metrics([0.0, 0.0], [1e200, -1e200])
        self.assertTrue(math.isfinite(metrics["rmse_log_return"]))
        self.assertAlmostEqual(metrics["rmse_log_return"], 1e200)

    def test_metrics_reject_unrepresentable_mean_absolute_error(self):
        from app.historical_forecasting import _metrics

        with self.assertRaisesRegex(ValueError, "forecast metrics must be finite"):
            _metrics([0.0, 0.0], [1.7e308, 1.7e308])

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


    def test_walk_forward_uses_expanding_pretest_history_and_aggregates(self):
        from app.historical_forecasting import evaluate_walk_forward_return_forecast

        report = evaluate_walk_forward_return_forecast(
            self.synthetic_closes(500),
            min_history_samples=100,
            test_window=20,
            step_size=20,
        )
        self.assertTrue(report["research_only"])
        self.assertGreaterEqual(report["window_count"], 5)
        self.assertEqual(report["window_count"], len(report["windows"]))
        previous_start = -1
        for window in report["windows"]:
            start = window["test_start_target_index"]
            end = window["test_end_target_index_exclusive"]
            self.assertGreater(start, previous_start)
            self.assertEqual(end - start, 20)
            self.assertEqual(window["history_samples"], start)
            self.assertEqual(
                window["pretest_mean_return_baseline"]["fit_samples"], start
            )
            self.assertEqual(window["model"]["sample_count"], 20)
            self.assertEqual(window["zero_return_baseline"]["sample_count"], 20)
            previous_start = start
        aggregate = report["aggregate_test_metrics"]["model"]["mae_log_return"]
        self.assertEqual(aggregate["window_count"], report["window_count"])
        self.assertTrue(math.isfinite(aggregate["mean"]))
        self.assertTrue(math.isfinite(aggregate["median"]))

    def test_walk_forward_rejects_overlapping_test_windows(self):
        from app.historical_forecasting import evaluate_walk_forward_return_forecast

        with self.assertRaisesRegex(ValueError, "step_size must be >= test_window"):
            evaluate_walk_forward_return_forecast(
                self.synthetic_closes(500),
                min_history_samples=100,
                test_window=20,
                step_size=10,
            )

    def test_legacy_walk_forward_rejects_overlapping_test_windows(self):
        with self.assertRaisesRegex(ValueError, "step_size must be >= test_window_size"):
            evaluate_walk_forward_forecast(
                self.synthetic_closes(500),
                min_train_samples=100,
                test_window_size=20,
                step_size=10,
            )

    def test_walk_forward_rejects_invalid_parameters_and_short_history(self):
        from app.historical_forecasting import evaluate_walk_forward_return_forecast

        prices = self.synthetic_closes(220)
        for kwargs in (
            {"min_history_samples": 39},
            {"test_window": 4},
            {"step_size": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    evaluate_walk_forward_return_forecast(prices, **kwargs)
        with self.assertRaisesRegex(ValueError, "insufficient history"):
            evaluate_walk_forward_return_forecast(
                self.synthetic_closes(100), min_history_samples=80, test_window=30
            )


    def test_metrics_rejects_subtraction_overflow(self):
        from app.historical_forecasting import _metrics
        with self.assertRaisesRegex(ValueError, "forecast errors must be finite"):
            _metrics([-1e308], [1e308])

    def test_walk_forward_rejects_invalid_step_size_overlap(self):
        from app.historical_forecasting import evaluate_walk_forward_return_forecast
        with self.assertRaisesRegex(ValueError, "step_size must be >= test_window"):
            evaluate_walk_forward_return_forecast(
                self.synthetic_closes(300), min_history_samples=80, test_window=20, step_size=10
            )
    def test_ridge_fit_rejects_invalid_shape_and_alpha(self):
        from app.historical_forecasting import _fit_ridge
        for features, targets, alpha, message in (
            ([], [], 0.1, "non-empty and aligned"),
            ([[1.0], [2.0]], [0.1], 0.1, "non-empty and aligned"),
            ([[1.0], [2.0, 3.0]], [0.1, 0.2], 0.1, "consistent non-zero width"),
            ([[1.0]], [0.1], float("nan"), "alpha must be finite and positive"),
            ([[True]], [0.1], 0.1, "features\\[0\\]\\[0\\] must be finite numeric"),
            ([[10**10000]], [0.1], 0.1, "features\\[0\\]\\[0\\] must be finite numeric"),
        ):
            with self.subTest(features=features, alpha=alpha):
                with self.assertRaisesRegex(ValueError, message):
                    _fit_ridge(features, targets, alpha)

    def test_ridge_prediction_rejects_mismatched_width_and_nonfinite_output(self):
        from app.historical_forecasting import _predict
        with self.assertRaisesRegex(ValueError, "feature width must match coefficient count"):
            _predict([0.0, 1.0], [[1.0, 2.0]])
        with self.assertRaisesRegex(ValueError, "forecast predictions must be finite"):
            _predict([0.0, 1e308, 1e308], [[1.0, 1.0]])

    def test_ridge_solver_rejects_malformed_or_nonfinite_system(self):
        from app.historical_forecasting import _solve_linear_system
        for matrix, vector, message in (
            ([[1.0, 2.0]], [1.0], "square matrix"),
            ([[float("inf")]], [1.0], "matrix\\[0\\]\\[0\\] must be finite numeric"),
            ([[1.0]], [float("nan")], "vector\\[0\\] must be finite numeric"),
            ([[1.0]], [10**10000], "vector\\[0\\] must be finite numeric"),
        ):
            with self.subTest(matrix=matrix, vector=vector):
                with self.assertRaisesRegex(ValueError, message):
                    _solve_linear_system(matrix, vector)


if __name__ == "__main__":
    unittest.main()
