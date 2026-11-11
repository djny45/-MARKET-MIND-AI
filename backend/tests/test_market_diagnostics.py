import unittest

from app.market_diagnostics import build_market_diagnostics


def bars(count=30, volume=100):
    return [
        {"close": 100 + i, "volume": volume + i}
        for i in range(count)
    ]


class MarketDiagnosticsTests(unittest.TestCase):
    def test_volume_volatility_and_drawdown_fields(self):
        result = build_market_diagnostics(bars())
        self.assertEqual(result["status"], "calculated")
        self.assertIn("relative_to_reference_average", result["volume"])
        self.assertIn("maximum_close_to_close_drawdown", result["path"])
        self.assertIn("label", result["volatility_regime"])

    def test_insufficient_data_is_explicit(self):
        self.assertEqual(build_market_diagnostics(bars(2))["status"], "insufficient_data")

    def test_invalid_price_or_volume_rejected(self):
        invalid = bars()
        invalid[-1]["volume"] = -1
        result = build_market_diagnostics(invalid)
        self.assertEqual(result["status"], "invalid_data")

    def test_non_finite_input_is_invalid_data(self):
        for field, value in (("close", float("nan")), ("volume", float("inf"))):
            sample = bars()
            sample[-1][field] = value
            with self.subTest(field=field), self.assertEqual(
                build_market_diagnostics(sample)["status"], "invalid_data"
            ):
                pass

    def test_extreme_finite_prices_report_numeric_overflow(self):
        sample = [
            {"close": 1e-308, "volume": 1},
            {"close": 1e308, "volume": 1},
            {"close": 1e308, "volume": 1},
        ]
        result = build_market_diagnostics(sample)
        self.assertEqual(result["status"], "numeric_overflow")
        self.assertIn("limitations", result)

    def test_window_validation(self):
        with self.assertRaises(ValueError):
            build_market_diagnostics(bars(), volume_window=1)


if __name__ == "__main__":
    unittest.main()
