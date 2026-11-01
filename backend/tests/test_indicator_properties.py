"""Seeded property checks against independent, test-local reference calculations.

These tests validate algebraic invariants and selected formulas. They are not
a substitute for external vendor reconciliation or predictive evaluation.
"""
import math
import random
import unittest

from app.indicators import sma, ema, returns, rsi, macd, bollinger, realized_volatility


def reference_sma(values, period):
    result = []
    for index in range(len(values)):
        window = values[max(0, index - period + 1):index + 1]
        result.append(sum(window) / len(window))
    return result


def reference_ema(values, period):
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def reference_sample_std(values):
    mean = sum(values) / len(values)
    return math.sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))


class IndicatorPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(20261101)
        cls.series = []
        for _ in range(30):
            value = rng.uniform(20.0, 200.0)
            row = []
            for _ in range(80):
                value = max(0.01, value + rng.uniform(-3.0, 3.0))
                row.append(value)
            cls.series.append(row)

    def test_sma_matches_independent_reference_for_seeded_series(self):
        for values in self.series:
            for period in (1, 2, 5, 14, 30):
                actual = sma(values, period)
                expected = reference_sma(values, period)
                for left, right in zip(actual, expected):
                    self.assertAlmostEqual(left, right, places=10)

    def test_sma_translation_and_positive_scale_equivariance(self):
        for values in self.series:
            baseline = sma(values, 7)
            translated = sma([x + 17.5 for x in values], 7)
            scaled = sma([x * 3.25 for x in values], 7)
            for a, b, c in zip(baseline, translated, scaled):
                self.assertAlmostEqual(b, a + 17.5, places=9)
                self.assertAlmostEqual(c, a * 3.25, places=8)

    def test_sma_window_is_bounded_by_window_extrema(self):
        for values in self.series:
            period = 9
            actual = sma(values, period)
            for index, value in enumerate(actual):
                window = values[max(0, index - period + 1):index + 1]
                self.assertGreaterEqual(value + 1e-12, min(window))
                self.assertLessEqual(value - 1e-12, max(window))

    def test_ema_matches_independent_recursive_reference(self):
        for values in self.series:
            for period in (1, 2, 5, 14, 30):
                actual = ema(values, period)
                expected = reference_ema(values, period)
                for left, right in zip(actual, expected):
                    self.assertAlmostEqual(left, right, places=10)

    def test_ema_constant_series_and_convex_hull_invariant(self):
        self.assertEqual(ema([42.0] * 25, 8), [42.0] * 25)
        for values in self.series:
            actual = ema(values, 12)
            for value in actual:
                self.assertGreaterEqual(value + 1e-10, min(values))
                self.assertLessEqual(value - 1e-10, max(values))

    def test_simple_returns_are_invariant_to_price_unit_scaling(self):
        for values in self.series:
            base = returns(values)
            scaled = returns([x * 1000.0 for x in values])
            for left, right in zip(base, scaled):
                self.assertAlmostEqual(left, right, places=12)

    def test_rsi_is_bounded_and_flat_series_is_neutral(self):
        for values in self.series:
            for value in rsi(values, 14):
                if value is not None:
                    self.assertGreaterEqual(value, 0.0)
                    self.assertLessEqual(value, 100.0)
        self.assertEqual(rsi([10.0] * 20, 5)[-1], 50.0)

    def test_macd_histogram_is_difference_of_line_and_signal(self):
        for values in self.series:
            result = macd(values, fast=5, slow=13, signal=4)
            for line, signal, histogram in zip(
                result["macd"], result["signal"], result["histogram"]
            ):
                self.assertAlmostEqual(histogram, line - signal, places=12)

    def test_bollinger_bands_are_symmetric_around_reference_sma(self):
        for values in self.series:
            period = 12
            bands = bollinger(values, period=period, deviations=2.0)
            middle = reference_sma(values, period)
            for index, (lower, center, upper) in enumerate(zip(
                bands["lower"], bands["middle"], bands["upper"]
            )):
                self.assertAlmostEqual(center, middle[index], places=10)
                self.assertAlmostEqual(upper - center, center - lower, places=10)
                self.assertGreaterEqual(upper + 1e-10, center)
                self.assertLessEqual(lower - 1e-10, center)

    def test_realized_volatility_is_invariant_to_price_unit_scaling(self):
        for values in self.series:
            base = realized_volatility(values)["per_observation"]
            scaled = realized_volatility([x * 7.0 for x in values])["per_observation"]
            self.assertAlmostEqual(base, scaled, places=12)

    def test_realized_volatility_matches_independent_sample_standard_deviation(self):
        for values in self.series:
            simple_returns = [values[i] / values[i - 1] - 1.0
                              for i in range(1, len(values))]
            expected = reference_sample_std(simple_returns)
            actual = realized_volatility(values)["per_observation"]
            self.assertAlmostEqual(actual, expected, places=12)


if __name__ == "__main__":
    unittest.main()
