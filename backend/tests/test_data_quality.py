import unittest
from datetime import datetime, timezone

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.data_quality import build_freshness_report


class FreshnessReportTests(unittest.TestCase):
    def make_batch(self, bars):
        return MarketDataBatch(
            symbol="TEST", interval="1h", status=DataStatus.HISTORICAL,
            source="fixture-provider",
            retrieved_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
            bars=bars,
        )

    def test_reports_fresh_data_from_newest_bar(self):
        bar = OHLCVBar(
            timestamp=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            open=10, high=12, low=9, close=11, volume=100,
        )
        report = build_freshness_report(
            self.make_batch([bar]),
            now=datetime(2026, 1, 1, 2, 30, tzinfo=timezone.utc),
            threshold_seconds=3600,
        )
        self.assertEqual(report.age_seconds, 1800)
        self.assertFalse(report.stale)
        self.assertEqual(report.source, "fixture-provider")

    def test_reports_stale_data(self):
        bar = OHLCVBar(
            timestamp="2026-01-01T00:00:00Z",
            open=10, high=12, low=9, close=11, volume=100,
        )
        report = build_freshness_report(
            self.make_batch([bar]),
            now=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            threshold_seconds=3600,
        )
        self.assertTrue(report.stale)
        self.assertEqual(report.age_seconds, 7200)

    def test_empty_batch_has_unknown_age_not_zero(self):
        report = build_freshness_report(
            self.make_batch([]),
            now=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            threshold_seconds=3600,
        )
        self.assertIsNone(report.age_seconds)
        self.assertIsNone(report.stale)
        self.assertIsNone(report.newest_bar_at)

    def test_rejects_naive_now_and_future_bar(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            build_freshness_report(
                self.make_batch([]), now=datetime(2026, 1, 1), threshold_seconds=1
            )
        future = OHLCVBar(
            timestamp="2026-01-01T04:00:00Z",
            open=10, high=12, low=9, close=11, volume=100,
        )
        with self.assertRaisesRegex(ValueError, "precede"):
            build_freshness_report(
                self.make_batch([future]),
                now=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
                threshold_seconds=3600,
            )


if __name__ == "__main__":
    unittest.main()
