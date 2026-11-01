import unittest

from app.session_calendar import build_session_gap_report


CALENDAR = {
    "name": "test-market", "market": "test",
    "timezone": "Asia/Kolkata", "weekdays": [0, 1, 2, 3, 4],
    "session_open": "09:15", "session_close": "10:15",
    "holidays": ["2026-01-02"],
}


def bar(timestamp, source="feed-a"):
    return {"timestamp": timestamp, "source": source}


class SessionGapTests(unittest.TestCase):
    def test_counts_missing_scheduled_intraday_bars_and_per_source(self):
        history = {"symbol": "TEST", "interval": "15m", "bars": [
            bar("2026-01-01T09:15:00+05:30"),
            bar("2026-01-01T09:45:00+05:30"),
            bar("2026-01-01T09:15:00+05:30", "feed-b"),
        ]}
        result = build_session_gap_report(history, CALENDAR)
        self.assertEqual(result["expected_scheduled_bar_count"], 4)
        self.assertEqual(result["source_reports"]["feed-a"]["missing_scheduled_count"], 2)
        self.assertEqual(result["source_reports"]["feed-b"]["missing_scheduled_count"], 3)
        self.assertEqual(result["source_reports"]["feed-a"]["outside_schedule_count"], 0)

    def test_holidays_and_weekends_are_not_scheduled(self):
        history = {"interval": "15m", "bars": [
            bar("2026-01-01T09:15:00+05:30"),
            bar("2026-01-03T09:15:00+05:30"),
        ]}
        result = build_session_gap_report(history, CALENDAR)
        self.assertEqual(result["scheduled_session_days"], 1)

    def test_timezone_equivalent_timestamp_matches_schedule(self):
        history = {"interval": "15m", "bars": [
            bar("2026-01-01T03:45:00Z"),
        ]}
        result = build_session_gap_report(history, CALENDAR)
        self.assertEqual(result["source_reports"]["feed-a"]["matched_scheduled_count"], 1)

    def test_invalid_timestamp_is_reported(self):
        result = build_session_gap_report(
            {"interval": "15m", "bars": [bar("no-timezone")]}, CALENDAR
        )
        self.assertEqual(result["status"], "insufficient_timestamps")
        self.assertEqual(len(result["invalid_timestamps"]), 1)

    def test_rejects_invalid_timezone_and_overnight_sessions(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            build_session_gap_report({"interval": "1h", "bars": [bar("2026-01-01T00:00:00Z")]},
                                     {**CALENDAR, "timezone": "Mars/Olympus"})
        with self.assertRaisesRegex(ValueError, "overnight"):
            build_session_gap_report({"interval": "1h", "bars": [bar("2026-01-01T00:00:00Z")]},
                                     {**CALENDAR, "session_open": "22:00", "session_close": "05:00"})

    def test_daily_bars_schedule_once_per_session_open(self):
        result = build_session_gap_report(
            {"interval": "1d", "bars": [bar("2026-01-01T09:15:00+05:30")]}, CALENDAR
        )
        self.assertEqual(result["expected_scheduled_bar_count"], 1)
        self.assertEqual(result["source_reports"]["feed-a"]["missing_scheduled_count"], 0)


if __name__ == "__main__":
    unittest.main()
