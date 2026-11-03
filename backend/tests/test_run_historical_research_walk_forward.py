"""Tests for historical runner walk-forward date mapping (synthetic bars only)."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from run_historical_research import _dataset_fingerprint, run


class HistoricalRunnerWalkForwardTests(unittest.IsolatedAsyncioTestCase):
    async def test_walk_forward_report_maps_test_windows_to_bar_timestamps(self):
        bars = []
        close = 100.0
        for index in range(260):
            close *= 1.0003 + (index % 7) * 0.00001
            timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
            bars.append(SimpleNamespace(
                timestamp=timestamp,
                open=close,
                high=close * 1.001,
                low=close * 0.999,
                close=close,
                adjusted_close=close,
                volume=1000 + index,
            ))
        batch = SimpleNamespace(
            bars=bars,
            symbol="TEST",
            source="synthetic_test_fixture",
            interval="1d",
            status=SimpleNamespace(value="ok"),
            retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            warnings=[],
        )

        class FakeAdapter:
            async def get_bars(self, symbol, interval, requested_bars):
                return batch

        with patch("run_historical_research.YahooFinanceAdapter", FakeAdapter):
            report = await run(
                "TEST", 260, walk_forward=True,
                min_train_samples=100, test_window_size=20, step_size=20,
            )

        self.assertEqual(report["evaluation_mode"], "expanding_walk_forward")
        windows = report["windows"]
        periods = report["evaluation_periods_by_window"]
        self.assertEqual(len(windows), len(periods))
        target_dates = [bar.timestamp.isoformat() for bar in bars[6:]]
        for window, period in zip(windows, periods):
            self.assertEqual(period["window_number"], window["window_number"])
            self.assertEqual(
                period["test_target_start"],
                target_dates[window["test_sample_start_index"]],
            )
            self.assertEqual(
                period["test_target_end"],
                target_dates[window["test_sample_end_index_exclusive"] - 1],
            )
        self.assertEqual(report["data"]["dataset_sha256"], _dataset_fingerprint(batch))
        self.assertEqual(len(report["data"]["dataset_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
