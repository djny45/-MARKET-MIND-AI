import unittest

from app.chart_research import build_chart_report


def history(status="historical", source="fixture"):
    bars = []
    for index in range(60):
        close = 100 + index * 0.5
        bars.append({
            "timestamp": f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
            "open": close - 0.2, "high": close + 1,
            "low": close - 1, "close": close, "volume": 1000,
            "status": status, "source": source,
            "retrieved_at": "2026-03-01T00:00:00+00:00",
        })
    return {"symbol": "TEST", "interval": "1d", "bars": bars}


class ChartResearchTests(unittest.TestCase):
    def test_report_has_indicators_and_no_execution(self):
        result = build_chart_report(history())
        self.assertEqual(result["bars_analyzed"], 60)
        self.assertIn("rsi14", result["indicators"])
        self.assertIn("atr14", result["indicators"])
        self.assertEqual(result["execution"], "disabled")
        self.assertEqual(result["observed_structure"]["moving_average_regime"],
                         "close_above_short_and_medium_average")

    def test_synthetic_data_is_warned(self):
        result = build_chart_report(history(status="synthetic"))
        self.assertTrue(any("synthetic" in warning.lower() for warning in result["warnings"]))

    def test_requires_two_bars(self):
        with self.assertRaises(ValueError):
            build_chart_report({"bars": []})


if __name__ == "__main__":
    unittest.main()
