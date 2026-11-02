import unittest
from app.historical_quality import build_historical_quality_diagnostics


class HistoricalQualityTests(unittest.TestCase):
    def bars(self, count=25):
        return [{"timestamp": f"2026-01-01T{(i // 60):02d}:{i % 60:02d}:00+00:00",
                 "open": 100, "high": 102, "low": 99, "close": 100 + i * 0.1,
                 "volume": 100 + (i % 3)} for i in range(count)]

    def test_spacing_reports_elapsed_time_without_filling_bars(self):
        bars = self.bars(3)
        bars[2]["timestamp"] = "2026-01-01T02:00:00+00:00"
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        self.assertEqual(result["timestamp_spacing"]["spacing_anomaly_count"], 1)
        self.assertEqual(len(bars), 3)
        self.assertIn("not modelled", result["timestamp_spacing"]["interpretation"])

    def test_outlier_flags_are_suppressed_for_insufficient_history(self):
        result = build_historical_quality_diagnostics({"interval": "15m", "bars": self.bars(8)})
        self.assertEqual(result["close_to_close_return_outliers"]["status"], "insufficient_history")
        self.assertEqual(result["volume_outliers"]["status"], "insufficient_history")

    def test_zero_mad_is_reported_as_unavailable(self):
        bars = self.bars(25)
        for bar in bars:
            bar["volume"] = 100
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        self.assertEqual(result["volume_outliers"]["status"], "unavailable_zero_mad")

    def test_outlier_flags_include_original_timestamp_and_value(self):
        bars = self.bars(30)
        # Keep a non-zero baseline MAD so the injected spike is statistically testable.
        bars[25]["close"] = 250
        bars[25]["volume"] = 900
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        price_flags = result["close_to_close_return_outliers"]["flagged_observations"]
        volume_flags = result["volume_outliers"]["flagged_observations"]
        self.assertTrue(any(item["bar_index"] == 25 and item["timestamp"] == bars[25]["timestamp"] for item in price_flags))
        self.assertTrue(any(item["bar_index"] == 25 and item["volume"] == 900 for item in volume_flags))
        self.assertEqual(next(item for item in price_flags if item["bar_index"] == 25)["previous_close"], 102.4)

    def test_timestamp_integrity_reports_invalid_duplicate_and_out_of_order(self):
        bars = self.bars(4)
        bars[1]["timestamp"] = bars[0]["timestamp"]
        bars[2]["timestamp"] = "not-a-timestamp"
        bars[3]["timestamp"] = "2025-12-31T23:59:00+00:00"
        result = build_historical_quality_diagnostics({"interval": "15m", "bars": bars})
        integrity = result["timestamp_integrity"]
        self.assertEqual(integrity["invalid_timestamp_count"], 1)
        self.assertEqual(integrity["duplicate_timestamp_count"], 1)
        self.assertEqual(integrity["duplicate_timestamps"][0]["first_bar_index"], 0)
        self.assertEqual(integrity["out_of_order_count"], 1)
        self.assertEqual(integrity["out_of_order_timestamps"][0]["bar_index"], 3)
        self.assertEqual(len(bars), 4)

    def test_equivalent_timezone_instants_are_duplicates(self):
        bars = self.bars(2)
        bars[1]["timestamp"] = "2026-01-01T01:00:00+01:00"
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        self.assertEqual(result["timestamp_integrity"]["duplicate_timestamp_count"], 1)

    def test_unsupported_interval_does_not_infer_spacing(self):
        result = build_historical_quality_diagnostics({"interval": "weekly", "bars": self.bars(4)})
        self.assertEqual(result["timestamp_spacing"]["status"], "unsupported_interval")
        self.assertIsNone(result["timestamp_spacing"]["expected_interval_seconds"])

    def test_non_finite_close_and_volume_are_reported_and_excluded(self):
        bars = self.bars(25)
        bars[5]["close"] = float("nan")
        bars[8]["close"] = float("inf")
        bars[10]["volume"] = float("inf")
        bars[12]["volume"] = float("nan")
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        invalid = result["invalid_numeric_values"]
        self.assertEqual(invalid["close_count"], 2)
        self.assertEqual(invalid["volume_count"], 2)
        self.assertEqual([item["bar_index"] for item in invalid["close_values"]], [5, 8])
        self.assertEqual([item["bar_index"] for item in invalid["volume_values"]], [10, 12])
        self.assertEqual(result["close_to_close_return_outliers"]["sample_count"], 20)
        self.assertNotIn(10, result["volume_outliers"]["flagged_bar_indices"])


if __name__ == "__main__":
    unittest.main()
