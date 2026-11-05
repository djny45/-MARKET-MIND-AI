"""Validation tests for the optional TA-Lib historical adapter."""
import importlib.util
import unittest

available = all(importlib.util.find_spec(name) is not None for name in ("pandas", "numpy"))


@unittest.skipUnless(available, "optional pandas/numpy research dependencies not installed")
class TALibResearchTests(unittest.TestCase):
    def setUp(self):
        import pandas as pd
        self.frame = pd.DataFrame({
            "Open": [10.0 + i * 0.1 for i in range(100)],
            "High": [10.5 + i * 0.1 for i in range(100)],
            "Low": [9.5 + i * 0.1 for i in range(100)],
            "Close": [10.2 + i * 0.1 for i in range(100)],
        })

    def test_missing_column_rejected(self):
        from app.ta_lib_research import analyze_historical_ohlcv
        with self.assertRaisesRegex(ValueError, "Missing required OHLC"):
            analyze_historical_ohlcv(self.frame.drop(columns=["Low"]))

    def test_nonfinite_ohlc_rejected(self):
        from app.ta_lib_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.loc[4, "Close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "NaN or infinite"):
            analyze_historical_ohlcv(bad)

    def test_bad_high_low_rejected(self):
        from app.ta_lib_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.loc[2, "High"] = 0
        with self.assertRaisesRegex(ValueError, "high is below"):
            analyze_historical_ohlcv(bad)

    def test_period_validation(self):
        from app.ta_lib_research import analyze_historical_ohlcv
        with self.assertRaisesRegex(ValueError, "periods must be"):
            analyze_historical_ohlcv(self.frame, rsi_period=1)
        with self.assertRaisesRegex(ValueError, "fast_period"):
            analyze_historical_ohlcv(self.frame, fast_period=26, slow_period=12)
        for invalid in (2.5, True):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "periods must be"):
                    analyze_historical_ohlcv(self.frame, rsi_period=invalid)

    @unittest.skipUnless(importlib.util.find_spec("talib") is not None, "TA-Lib package not installed")
    def test_indicator_output_keys(self):
        from app.ta_lib_research import analyze_historical_ohlcv
        result = analyze_historical_ohlcv(self.frame)
        self.assertEqual(set(result), {
            "rsi", "macd", "macd_signal", "macd_histogram", "atr",
            "sma_20", "ema_20", "bbands_upper", "bbands_middle", "bbands_lower",
        })
        self.assertEqual(len(result["rsi"]), len(self.frame))


if __name__ == "__main__":
    unittest.main()
