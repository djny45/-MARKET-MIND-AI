import unittest
from datetime import datetime, timezone

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.market_data_quality import build_market_data_quality_report


class MarketDataQualityReportTests(unittest.TestCase):
    def make_batch(self, bars, status=DataStatus.HISTORICAL, warnings=None):
        return MarketDataBatch(
            symbol="test", interval="1h", status=status, source="test-provider",
            retrieved_at=datetime(2026, 1, 1, 4, tzinfo=timezone.utc),
            bars=bars, warnings=warnings or [],
        )

    def bar(self, hour):
        return OHLCVBar(
            timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
            open=10, high=12, low=9, close=11, volume=100,
        )

    def test_reports_gaps_staleness_and_historical_provenance(self):
        batch = self.make_batch([self.bar(0), self.bar(2)])
        report = build_market_data_quality_report(
            batch, now=datetime(2026, 1, 1, 4, tzinfo=timezone.utc),
            freshness_threshold_seconds=3600,
        )
        codes = {finding.code for finding in report.findings}
        self.assertEqual(report.bar_count, 2)
        self.assertEqual(len(report.missing_candle_timestamps), 1)
        self.assertTrue({"CANDLE_GAPS", "STALE_DATA", "HISTORICAL_DATA"} <= codes)

    def test_empty_batch_and_synthetic_data_are_explicit(self):
        batch = self.make_batch([], status=DataStatus.SYNTHETIC, warnings=["fixture only"])
        report = build_market_data_quality_report(
            batch, now=datetime(2026, 1, 1, 4, tzinfo=timezone.utc),
            freshness_threshold_seconds=3600,
        )
        codes = {finding.code for finding in report.findings}
        self.assertIsNone(report.freshness.age_seconds)
        self.assertTrue({"EMPTY_BATCH", "SYNTHETIC_DATA", "PROVIDER_WARNINGS"} <= codes)

    def test_contiguous_batch_has_no_gap_finding(self):
        batch = self.make_batch([self.bar(1), self.bar(2)])
        report = build_market_data_quality_report(
            batch, now=datetime(2026, 1, 1, 2, 30, tzinfo=timezone.utc),
            freshness_threshold_seconds=3600,
        )
        self.assertNotIn("CANDLE_GAPS", {finding.code for finding in report.findings})


if __name__ == "__main__":
    unittest.main()
