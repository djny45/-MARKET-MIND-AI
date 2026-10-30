import unittest

from app.deep_analysis import build_data_quality_report, build_deep_analysis_report


def history(interval="1h", count=60):
    bars = []
    for index in range(count):
        close = 100 + index * 0.25
        bars.append({
            "timestamp": f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
            "open": close - 0.1, "high": close + 0.8,
            "low": close - 0.8, "close": close, "volume": 100,
            "status": "historical", "source": "test",
            "retrieved_at": "2026-03-01T00:00:00+00:00",
        })
    return {"symbol": "TEST", "interval": interval, "bars": bars}


class DeepAnalysisTests(unittest.TestCase):
    def test_integrates_chart_and_quality_sections(self):
        result = build_deep_analysis_report("TEST", {"1h": history()})
        self.assertIn("data_quality", result["timeframes"]["1h"])
        self.assertIn("chart_research", result["timeframes"]["1h"])
        self.assertEqual(result["execution"], "disabled")

    def test_flags_duplicate_and_invalid_ohlc(self):
        item = history(count=4)
        item["bars"][1]["timestamp"] = item["bars"][0]["timestamp"]
        item["bars"][2]["high"] = item["bars"][2]["low"] - 1
        result = build_data_quality_report(item)
        self.assertEqual(result["quality_status"], "issues_detected")
        self.assertTrue(result["duplicate_timestamps"])
        self.assertTrue(result["invalid_ohlc_indices"])

    def test_malformed_numeric_history_keeps_quality_report_available(self):
        history = {"bars": [
            {"timestamp": f"2026-01-0{i}T00:00:00+00:00", "open": 10, "high": 11,
             "low": 9, "close": close, "volume": 100}
            for i, close in enumerate([10, "bad", 12], start=1)
        ]}
        report = build_deep_analysis_report("BTCUSD", {"1h": history})
        self.assertEqual(report["timeframes"]["1h"]["market_diagnostics"]["status"], "invalid_data")
        self.assertEqual(report["timeframes"]["1h"]["chart_research"]["status"], "unavailable_invalid_or_incomplete_data")

    def test_insufficient_timeframe_is_reported(self):
        result = build_deep_analysis_report("TEST", {"15m": history(count=1)})
        self.assertEqual(result["coverage"]["timeframes_with_insufficient_bars"], ["15m"])
        self.assertIsNone(result["timeframes"]["15m"]["chart_research"])

    def test_empty_histories_rejected(self):
        with self.assertRaises(ValueError):
            build_deep_analysis_report("TEST", {})


if __name__ == "__main__":
    unittest.main()
