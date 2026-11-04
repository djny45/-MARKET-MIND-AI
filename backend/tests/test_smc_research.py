"""Tests for the optional SMC historical research adapter.

The optional pandas dependency is intentionally not required by core CI.
"""
import importlib.util
import unittest
from unittest.mock import patch

if importlib.util.find_spec("pandas") is None or importlib.util.find_spec("numpy") is None:
    pandas_available = False
else:
    pandas_available = True


@unittest.skipUnless(pandas_available, "optional pandas/numpy research dependencies not installed")
class SMCResearchAdapterTests(unittest.TestCase):
    def setUp(self):
        import pandas as pd
        self.pd = pd
        self.frame = pd.DataFrame({
            "open": [10.0 + i * 0.1 for i in range(120)],
            "high": [10.5 + i * 0.1 for i in range(120)],
            "low": [9.5 + i * 0.1 for i in range(120)],
            "close": [10.2 + i * 0.1 for i in range(120)],
            "volume": [100.0] * 120,
        })

    def test_missing_ohlc_column_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        with self.assertRaisesRegex(ValueError, "Missing required OHLC"):
            analyze_historical_ohlcv(self.frame.drop(columns=["low"]), swing_length=5)

    def test_nan_ohlc_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.loc[3, "close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "NaN or infinite"):
            analyze_historical_ohlcv(bad, swing_length=5)

    def test_inconsistent_high_low_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.loc[3, "high"] = 1.0
        with self.assertRaisesRegex(ValueError, "high is below"):
            analyze_historical_ohlcv(bad, swing_length=5)

    def test_insufficient_history_rejected_before_smc_import(self):
        from app.smc_research import analyze_historical_ohlcv
        with self.assertRaisesRegex(ValueError, "Not enough bars"):
            analyze_historical_ohlcv(self.frame.iloc[:10], swing_length=5)

    def test_returns_expected_indicator_keys(self):
        from app.smc_research import analyze_historical_ohlcv
        from app.vendor.smartmoneyconcepts import smc

        fake_results = {name: object() for name in (
            "fvg", "swing_highs_lows", "bos_choch", "ob", "liquidity", "retracements"
        )}
        with patch.object(smc, "fvg", return_value=fake_results["fvg"]), \
             patch.object(smc, "swing_highs_lows", return_value=fake_results["swing_highs_lows"]), \
             patch.object(smc, "bos_choch", return_value=fake_results["bos_choch"]), \
             patch.object(smc, "ob", return_value=fake_results["ob"]), \
             patch.object(smc, "liquidity", return_value=fake_results["liquidity"]), \
             patch.object(smc, "retracements", return_value=fake_results["retracements"]):
            result = analyze_historical_ohlcv(self.frame, swing_length=5)
        self.assertEqual(set(result), set(fake_results))
        self.assertIs(result["swing_highs_lows"], fake_results["swing_highs_lows"])


if __name__ == "__main__":
    unittest.main()
