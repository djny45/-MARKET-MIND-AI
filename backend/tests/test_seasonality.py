import unittest

from app.seasonality import build_seasonality_report


class SeasonalityTests(unittest.TestCase):
    def test_groups_consecutive_returns_by_weekday_and_month(self):
        bars = [
            {"timestamp": "2026-01-05T00:00:00Z", "close": 100},
            {"timestamp": "2026-01-06T00:00:00Z", "close": 110},
            {"timestamp": "2026-01-07T00:00:00Z", "close": 99},
            {"timestamp": "2026-02-02T00:00:00Z", "close": 108.9},
        ]
        result = build_seasonality_report(bars)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["return_observations"], 3)
        self.assertEqual(result["by_weekday"][0]["bucket"], "Tuesday")
        self.assertEqual(result["by_weekday"][0]["sample_count"], 1)
        self.assertEqual(result["by_calendar_month"][0]["bucket"], "January")
        self.assertEqual(result["by_calendar_month"][0]["sample_count"], 2)
        self.assertAlmostEqual(result["by_calendar_month"][0]["mean_return_pct"], -0.5, places=5)

    def test_skips_invalid_timezone_and_non_finite_close(self):
        bars = [
            {"timestamp": "2026-01-01T00:00:00", "close": 100},
            {"timestamp": "2026-01-02T00:00:00Z", "close": 101},
            {"timestamp": "2026-01-03T00:00:00Z", "close": float("nan")},
        ]
        result = build_seasonality_report(bars)
        self.assertEqual(result["skipped_observations"], 2)
        self.assertEqual(result["return_observations"], 0)
        self.assertEqual(result["status"], "insufficient_valid_observations")

    def test_empty_input_is_explicitly_unavailable(self):
        result = build_seasonality_report([])
        self.assertEqual(result["status"], "insufficient_valid_observations")
        self.assertEqual(result["by_weekday"], [])
        self.assertEqual(result["by_calendar_month"], [])

    def test_equal_timestamps_do_not_create_return_observation(self):
        bars = [
            {"timestamp": "2026-01-01T00:00:00Z", "close": 100},
            {"timestamp": "2026-01-01T00:00:00+00:00", "close": 101},
            {"timestamp": "2026-01-02T00:00:00Z", "close": 102},
        ]
        result = build_seasonality_report(bars)
        self.assertEqual(result["return_observations"], 1)
        self.assertEqual(result["skipped_observations"], 1)


if __name__ == "__main__":
    unittest.main()
