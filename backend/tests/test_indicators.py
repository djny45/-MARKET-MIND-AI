import unittest

from app.indicators import (
    sma, ema, returns, rsi, macd, bollinger, realized_volatility,
)


class IndicatorTests(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4], 2), [1.0, 1.5, 2.5, 3.5])

    def test_ema(self):
        self.assertEqual(len(ema([1, 2, 3], 2)), 3)

    def test_returns(self):
        self.assertAlmostEqual(returns([100, 110, 99])[0], .1)

    def test_rsi(self):
        self.assertTrue(all(x is None or 0 <= x <= 100 for x in rsi(list(range(1, 40)))))

    def test_macd(self):
        self.assertEqual(len(macd(list(range(1, 40)))["histogram"]), 39)

    def test_bollinger(self):
        self.assertEqual(len(bollinger(list(range(1, 25)))["upper"]), 24)

    def test_volatility(self):
        self.assertGreater(realized_volatility([100, 101, 99, 102])["per_observation"], 0)

    def test_all_indicators_reject_non_finite_observations(self):
        functions = (
            lambda values: sma(values, 2),
            lambda values: ema(values, 2),
            returns,
            lambda values: rsi(values, 2),
            macd,
            lambda values: bollinger(values, 2),
            realized_volatility,
        )
        for function in functions:
            for invalid in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(function=function, invalid=invalid):
                    with self.assertRaises(ValueError):
                        function([1.0, invalid, 2.0])

    def test_indicator_rejects_non_finite_derived_values(self):
        with self.assertRaises(ValueError):
            sma([1e308, 1e308], 2)
        with self.assertRaises(ValueError):
            returns([1e-308, 1e308])

    def test_variance_overflow_is_reported_as_value_error(self):
        with self.assertRaises(ValueError):
            bollinger([1e308, -1e308, 1e308], period=3)
        with self.assertRaises(ValueError):
            realized_volatility([1.0, 1e154, 1.0, 1e154])

    def test_realized_volatility_requires_finite_positive_annualization(self):
        for value in (float("nan"), float("inf"), 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                realized_volatility([100, 101, 99], annualization=value)


if __name__ == "__main__":
    unittest.main()
