import unittest
from unittest.mock import patch

from app.market_data import DataStatus
from app.yahoo_finance_adapter import YahooFinanceAdapter


def chart_payload():
    return {
        "chart": {
            "error": None,
            "result": [{
                "timestamp": [1767225600, 1767312000],
                "indicators": {"quote": [{
                    "open": [100, 101], "high": [103, 104], "low": [99, 100],
                    "close": [102, 103], "volume": [1000, 1100],
                }]}
            }]
        }
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
        self.assertTrue(batch.warnings)

    async def test_rejects_invalid_symbol_interval_and_limit(self):
        adapter = YahooFinanceAdapter()
        for args in [("", "1d", 5), ("AAPL", "5m", 5), ("AAPL", "1d", 0), ("AAPL", "1d", 5001)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                await adapter.get_bars(*args)

    async def test_rejects_4h_instead_of_mislabelling_hourly_data(self):
        adapter = YahooFinanceAdapter()
        with self.assertRaisesRegex(ValueError, "4h aggregation is not supported"):
            await adapter.get_bars("AAPL", "4h", 10)

    async def test_negative_provider_volume_is_not_silently_clamped(self):
        adapter = YahooFinanceAdapter()
        payload = chart_payload()
        payload["chart"]["result"][0]["indicators"]["quote"][0]["volume"][0] = -10
        with patch.object(adapter, "_fetch_chart", return_value=payload):
            with self.assertRaises(ValueError):
                await adapter.get_bars("AAPL", "1d", 10)

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
