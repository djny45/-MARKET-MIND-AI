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

    def test_unsupported_interval_does_not_infer_spacing(self):
        result = build_historical_quality_diagnostics({"interval": "weekly", "bars": self.bars(4)})
        self.assertEqual(result["timestamp_spacing"]["status"], "unsupported_interval")
        self.assertIsNone(result["timestamp_spacing"]["expected_interval_seconds"])


if __name__ == "__main__":
    unittest.main()
