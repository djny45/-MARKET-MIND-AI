import unittest

from app.performance import max_drawdown, performance_metrics


class PerformanceTests(unittest.TestCase):
    def test_drawdown(self):
        self.assertAlmostEqual(max_drawdown([100, 120, 90, 110]), -0.25)

    def test_flat_prices(self):
        result = performance_metrics([100, 100, 100, 100], periods_per_year=252)
        self.assertEqual(result["cumulative_return"], 0)
        self.assertIsNone(result["annualized_sharpe"])

    def test_benchmark_metrics(self):
        result = performance_metrics(
            [100, 102, 101, 104, 106], [100, 101, 100, 102, 103], 252
        )
        self.assertIsNotNone(result["beta"])
        self.assertIsNotNone(result["correlation_to_benchmark"])

    def test_invalid_prices(self):
        with self.assertRaises(ValueError):
            performance_metrics([100, 0, 101])

    def test_benchmark_length(self):
        with self.assertRaises(ValueError):
            performance_metrics([100, 101, 102], [100, 101])

    def test_non_finite_risk_free_rate_is_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                performance_metrics([100, 101, 102], risk_free_rate=value)

    def test_non_finite_or_non_positive_annualization_is_rejected(self):
        for value in (float("nan"), float("inf"), 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                performance_metrics([100, 101, 102], periods_per_year=value)

    def test_invalid_benchmark_prices_are_rejected(self):
        for prices in ([100, 0, 102], [100, -1, 102], [100, float("nan"), 102]):
            with self.subTest(prices=prices), self.assertRaises(ValueError):
                performance_metrics([100, 101, 102], benchmark=prices)

    def test_overflowing_primary_returns_are_rejected(self):
        with self.assertRaises(ValueError):
            performance_metrics([1e-308, 1e308, 1e308])

    def test_overflowing_cumulative_return_is_rejected(self):
        with self.assertRaises(ValueError):
            performance_metrics([1e-308, 1e-308, 1e308])

    def test_overflowing_benchmark_returns_are_rejected(self):
        with self.assertRaises(ValueError):
            performance_metrics([100, 101, 102], benchmark=[1e-308, 1e308, 1e308])

    def test_benchmark_requires_three_observations(self):
        with self.assertRaises(ValueError):
            performance_metrics([100, 101, 102], benchmark=[100, 101])


if __name__ == "__main__":
    unittest.main()
