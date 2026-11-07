import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from app.market_data import DataStatus
from app.yahoo_finance_adapter import YahooFinanceAdapter


def chart_payload():
    return {
        "chart": {
            "error": None,
            "result": [{
                "timestamp": [1767225600, 1767312000],
                "indicators": {
                    "quote": [{
                        "open": [100, 101], "high": [103, 104], "low": [99, 100],
                        "close": [102, 103], "volume": [1000, 1100],
                    }],
                    "adjclose": [{"adjclose": [101.5, 102.7]}],
                },
            }],
        },
    }

class YahooFinanceAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_chart_response_to_normalized_historical_batch(self):
        adapter = YahooFinanceAdapter()
        with patch.object(adapter, "_fetch_chart", return_value=chart_payload()):
            batch = await adapter.get_bars("aapl", "1d", 1)
        self.assertEqual(batch.symbol, "AAPL")
        self.assertEqual(batch.status, DataStatus.HISTORICAL)
        self.assertEqual(batch.source, "yahoo-finance-chart")
        self.assertEqual(len(batch.bars), 1)
        self.assertEqual(batch.bars[0].close, 103.0)
        self.assertEqual(batch.bars[0].adjusted_close, 102.7)
        self.assertTrue(batch.warnings)

    async def test_four_hour_interval_aggregates_complete_hourly_bars(self):
        payload = chart_payload()
        result = payload["chart"]["result"][0]
        start = 1767225600
        result["timestamp"] = [start + hour * 3600 for hour in range(4)]
        quote = result["indicators"]["quote"][0]
        quote["open"] = [100, 101, 102, 103]
        quote["high"] = [102, 104, 103, 105]
        quote["low"] = [99, 100, 101, 102]
        quote["close"] = [101, 102, 102.5, 104]
        quote["volume"] = [10, 20, 30, 40]
        result["indicators"]["adjclose"][0]["adjclose"] = [100.5, 101.5, 102, 103.5]

        adapter = YahooFinanceAdapter()
        with patch.object(adapter, "_fetch_chart", return_value=payload):
            batch = await adapter.get_bars("AAPL", "4h", 10)

        self.assertEqual(batch.interval, "4h")
        self.assertEqual(len(batch.bars), 1)
        bar = batch.bars[0]
        self.assertEqual(bar.timestamp.timestamp(), start)
        self.assertEqual((bar.open, bar.high, bar.low, bar.close), (100, 105, 99, 104))
        self.assertEqual(bar.volume, 100)
        self.assertEqual(bar.adjusted_close, 103.5)
        self.assertTrue(any("aggregated from complete" in warning for warning in batch.warnings))

    async def test_four_hour_interval_discards_incomplete_hourly_bucket(self):
        adapter = YahooFinanceAdapter()
        with patch.object(adapter, "_fetch_chart", return_value=chart_payload()):
            with self.assertRaisesRegex(ValueError, "No OHLCV bars returned"):
                await adapter.get_bars("AAPL", "4h", 10)

    async def test_skips_non_finite_negative_volume_and_invalid_ohlc_rows(self):
        payload = chart_payload()
        result = payload["chart"]["result"][0]
        result["timestamp"].extend([1767398400, 1767484800, 1767571200, 1767657600])
        quote = result["indicators"]["quote"][0]
        quote["open"].extend([float("nan"), 101, 101, 101])
        quote["high"].extend([104, float("inf"), 104, 104])
        quote["low"].extend([100, 100, 100, 105])
        quote["close"].extend([103, 103, 103, 102])
        quote["volume"].extend([1000, 1000, -1, 1000])
        adapter = YahooFinanceAdapter()
        with patch.object(adapter, "_fetch_chart", return_value=payload):
            batch = await adapter.get_bars("AAPL", "1d", 100)
        self.assertEqual(len(batch.bars), 2)
        self.assertEqual([bar.close for bar in batch.bars], [102.0, 103.0])


    async def test_malformed_timestamp_is_reported_as_invalid_chart_data(self):
        payload = chart_payload()
        payload["chart"]["result"][0]["timestamp"][0] = 10**100
        adapter = YahooFinanceAdapter()
        with patch.object(adapter, "_fetch_chart", return_value=payload):
            with self.assertRaisesRegex(ValueError, "valid OHLCV chart data"):
                await adapter.get_bars("AAPL", "1d", 10)

    async def test_rejects_invalid_symbol_interval_and_limit(self):
        adapter = YahooFinanceAdapter()
        for args in [("", "1d", 5), ("AAPL", "5m", 5), ("AAPL", "1d", 0), ("AAPL", "1d", 5001)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                await adapter.get_bars(*args)

    async def test_empty_provider_result_raises_clear_error(self):
        adapter = YahooFinanceAdapter()
        payload = {"chart": {"error": None, "result": [{"timestamp": [], "indicators": {"quote": [{}]}}]}}
        with patch.object(adapter, "_fetch_chart", return_value=payload):
            with self.assertRaisesRegex(ValueError, "No OHLCV bars"):
                await adapter.get_bars("AAPL")

    def test_timeout_bounds_are_validated(self):
        with self.assertRaises(ValueError):
            YahooFinanceAdapter(timeout_seconds=0.1)


if __name__ == "__main__":
    unittest.main()
