import unittest
import math
from app.historical_quality import build_historical_quality_diagnostics, _median, _mad_flags, _safe_round


class HistoricalQualityTests(unittest.TestCase):
    def bars(self, count=25):
        return [{"timestamp": f"2026-01-01T{(i // 60):02d}:{i % 60:02d}:00+00:00",
                 "open": 100, "high": 102, "low": 99, "close": 100 + i * 0.1,
                 "volume": 100 + (i % 3)} for i in range(count)]

    def test_history_must_be_mapping(self):
        for invalid in (None, [], "history"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "history must be a mapping"):
                    build_historical_quality_diagnostics(invalid)

    def test_bars_must_be_list_or_tuple(self):
        for invalid in (None, {}, "bars"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "history bars must be a list or tuple"):
                    build_historical_quality_diagnostics({"bars": invalid})

    def test_malformed_bar_rows_are_reported_and_skipped(self):
        bars = self.bars(25)
        bars[7] = "malformed-row"
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        self.assertEqual(result["bars_checked"], 25)
        self.assertEqual(result["malformed_bar_count"], 1)
        self.assertEqual(result["malformed_bar_indices"], [7])
        self.assertEqual(result["timestamp_integrity"]["invalid_timestamp_count"], 1)
        self.assertEqual(result["volume_outliers"]["sample_count"], 24)

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

    def test_non_finite_close_and_volume_values_are_excluded(self):
        bars = self.bars(25)
        bars[5]["close"] = float("nan")
        bars[6]["volume"] = float("inf")
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        price_result = result["close_to_close_return_outliers"]
        volume_result = result["volume_outliers"]
        self.assertEqual(price_result["sample_count"], 22)
        self.assertEqual(volume_result["sample_count"], 24)
        self.assertTrue(all(math.isfinite(item["return_pct"]) for item in price_result["flagged_observations"]))
        self.assertTrue(all(math.isfinite(item["volume"]) for item in volume_result["flagged_observations"]))

    def test_overflowing_close_to_close_return_is_skipped(self):
        bars = self.bars(25)
        bars[4]["close"] = 1e-308
        bars[5]["close"] = 1e308
        result = build_historical_quality_diagnostics({"interval": "1h", "bars": bars})
        self.assertEqual(result["close_to_close_return_outliers"]["sample_count"], 23)
        self.assertTrue(all(math.isfinite(value) for value in result["close_to_close_return_outliers"].get("flagged_observations", []) for value in [value["return_pct"]]))

    def test_safe_round_rejects_nonfinite_derived_metrics(self):
        self.assertIsNone(_safe_round(1e308 * 100, 6))
        self.assertIsNone(_safe_round(float("inf"), 3))
        self.assertEqual(_safe_round(1.23456789, 4), 1.2346)

    def test_median_of_extreme_finite_values_does_not_overflow(self):
        self.assertEqual(_median([1e308, 1e308]), 1e308)
        self.assertTrue(math.isfinite(_median([1e308, 1e308])))

    def test_mad_reports_unavailable_when_finite_values_overflow_deviation(self):
        values = [-1e308, 1e308] + [1e308] * 23
        result = _mad_flags(values)
        self.assertEqual(result["status"], "unavailable_nonfinite_deviation")
        self.assertEqual(result["sample_count"], 25)
        self.assertEqual(result["flagged_indices"], [])


    def test_unhashable_interval_metadata_is_reported_as_unsupported(self):
        for interval in ([], {}, None):
            with self.subTest(interval=interval):
                result = build_historical_quality_diagnostics({
                    "interval": interval, "bars": self.bars(4)
                })
                self.assertEqual(
                    result["timestamp_spacing"]["status"], "unsupported_interval"
                )
                self.assertIsNone(
                    result["timestamp_spacing"]["expected_interval_seconds"]
                )

    def test_unsupported_interval_does_not_infer_spacing(self):
        result = build_historical_quality_diagnostics({"interval": "weekly", "bars": self.bars(4)})
        self.assertEqual(result["timestamp_spacing"]["status"], "unsupported_interval")
        self.assertIsNone(result["timestamp_spacing"]["expected_interval_seconds"])


if __name__ == "__main__":
    unittest.main()
