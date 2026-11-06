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

    def _mock_indicator_tables(self, frame):
        from app.vendor.smartmoneyconcepts import smc
        tables = {
            name: self.pd.DataFrame({"value": range(len(frame))})
            for name in (
                "fvg", "swing_highs_lows", "bos_choch",
                "order_blocks", "liquidity", "retracements",
            )
        }
        patches = [
            patch.object(smc, "fvg", return_value=tables["fvg"]),
            patch.object(smc, "swing_highs_lows", return_value=tables["swing_highs_lows"]),
            patch.object(smc, "bos_choch", return_value=tables["bos_choch"]),
            patch.object(smc, "ob", return_value=tables["order_blocks"]),
            patch.object(smc, "liquidity", return_value=tables["liquidity"]),
            patch.object(smc, "retracements", return_value=tables["retracements"]),
        ]
        return tables, patches

    def test_missing_ohlc_column_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        with self.assertRaisesRegex(ValueError, "Missing required OHLC"):
            analyze_historical_ohlcv(self.frame.drop(columns=["low"]), swing_length=5)


    def test_duplicate_columns_after_normalization_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.columns = [" Open ", "open", "low", "close", "volume"]
        with self.assertRaisesRegex(ValueError, "Duplicate columns after case/whitespace normalization"):
            analyze_historical_ohlcv(bad, swing_length=5)

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

    def test_nonpositive_prices_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.loc[0, ["open", "high", "low", "close"]] = [0.0, 1.0, 0.0, 0.5]
        with self.assertRaisesRegex(ValueError, "strictly positive"):
            analyze_historical_ohlcv(bad, swing_length=5)

    def test_insufficient_history_rejected_before_smc_import(self):
        from app.smc_research import analyze_historical_ohlcv
        with self.assertRaisesRegex(ValueError, "Not enough bars"):
            analyze_historical_ohlcv(self.frame.iloc[:10], swing_length=5)

    def test_liquidity_range_must_be_finite_numeric_not_bool(self):
        from app.smc_research import analyze_historical_ohlcv
        for invalid in (None, "0.01", True, float("nan"), float("inf"), 0, -0.1, 1.1):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite number in \\(0, 1\\]"):
                    analyze_historical_ohlcv(self.frame, swing_length=5, liquidity_range_percent=invalid)

    def test_swing_length_must_be_positive_integer_not_bool(self):
        from app.smc_research import analyze_historical_ohlcv
        for invalid in (0, -1, 2.5, True):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    analyze_historical_ohlcv(self.frame, swing_length=invalid)

    def test_missing_volume_skips_order_blocks_without_fabricating_volume(self):
        from app.smc_research import analyze_historical_ohlcv
        from app.vendor.smartmoneyconcepts import smc
        frame = self.frame.drop(columns=["volume"])
        with patch.object(smc, "fvg"), \
             patch.object(smc, "swing_highs_lows", return_value=self.pd.DataFrame(index=range(len(frame)))), \
             patch.object(smc, "bos_choch"), \
             patch.object(smc, "ob") as order_blocks, \
             patch.object(smc, "liquidity"), \
             patch.object(smc, "retracements"):
            result = analyze_historical_ohlcv(frame, swing_length=5)

        order_blocks.assert_not_called()
        self.assertIsNone(result["order_blocks"])
        self.assertIn("requires a volume column", result["research_metadata"]["skipped_indicators"]["order_blocks"])

    def test_invalid_volume_rejected(self):
        from app.smc_research import analyze_historical_ohlcv
        bad = self.frame.copy()
        bad.loc[2, "volume"] = -1
        with self.assertRaisesRegex(ValueError, "Volume must be non-negative"):
            analyze_historical_ohlcv(bad, swing_length=5)

    def test_indicator_tables_preserve_input_timestamp_index(self):
        from app.smc_research import analyze_historical_ohlcv
        frame = self.frame.copy()
        frame.index = self.pd.date_range("2024-01-01", periods=len(frame), freq="h")
        tables, patches = self._mock_indicator_tables(frame)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = analyze_historical_ohlcv(frame, swing_length=5)

        for name, table in tables.items():
            self.pd.testing.assert_index_equal(result[name].index, frame.index)
            self.pd.testing.assert_index_equal(table.index, frame.index)

    def test_metadata_warns_about_future_bar_confirmation(self):
        from app.smc_research import analyze_historical_ohlcv
        from app.vendor.smartmoneyconcepts import smc

        with patch.object(smc, "fvg"), \
             patch.object(smc, "swing_highs_lows", return_value=self.pd.DataFrame(index=range(len(self.frame)))), \
             patch.object(smc, "bos_choch"), \
             patch.object(smc, "ob"), \
             patch.object(smc, "liquidity"), \
             patch.object(smc, "retracements"):
            result = analyze_historical_ohlcv(self.frame, swing_length=7)

        metadata = result["research_metadata"]
        self.assertTrue(metadata["research_only"])
        self.assertTrue(metadata["lookahead_bias_possible"])
        self.assertEqual(metadata["swing_confirmation_bars"], 7)
        self.assertIn("confirmation timestamp", metadata["warning"])


if __name__ == "__main__":
    unittest.main()
