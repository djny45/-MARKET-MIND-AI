import unittest

from app.multi_timeframe import build_multi_timeframe_report


def history(interval, count=60):
    bars = []
    for index in range(count):
        close = 100 + index * 0.4
        bars.append({
            "timestamp": f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
            "open": close - 0.1, "high": close + 0.8,
            "low": close - 0.8, "close": close, "volume": 100,
            "status": "historical", "source": "test",
            "retrieved_at": "2026-03-01T00:00:00+00:00",
        })
    return {"symbol": "TEST", "interval": interval, "bars": bars}


class MultiTimeframeTests(unittest.TestCase):
    def test_multiple_intervals_are_analyzed(self):
        result = build_multi_timeframe_report("TEST", {
            "15m": history("15m"), "1h": history("1h")
        })
        self.assertEqual(result["timeframes_analyzed"], ["15m", "1h"])
        self.assertIn("cross_timeframe_comparison", result)
        self.assertEqual(result["execution"], "disabled")

    def test_insufficient_interval_is_reported_not_fabricated(self):
        result = build_multi_timeframe_report("TEST", {
            "15m": history("15m", 1), "1d": history("1d")
        })
        self.assertEqual(result["timeframes_missing_or_insufficient"], ["15m"])
        self.assertNotIn("15m", result["reports"])

    def test_rejects_unknown_interval(self):
        with self.assertRaises(ValueError):
            build_multi_timeframe_report("TEST", {"5m": history("5m")})


if __name__ == "__main__":
    unittest.main()
