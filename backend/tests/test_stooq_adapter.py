import unittest
from unittest.mock import patch

from app.market_data import DataStatus
from app.stooq_adapter import StooqAdapter


CSV = """Date,Open,High,Low,Close,Volume
2026-01-03,103,106,102,105,1200
2026-01-02,102,104,101,103,1100
2026-01-01,100,103,99,102,1000
"""


class StooqAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_csv_to_ascending_historical_bars(self):
        adapter = StooqAdapter()
        with patch.object(adapter, "_fetch_csv", return_value=CSV):
            batch = await adapter.get_bars("AAPL.US", "1d", 2)
        self.assertEqual(batch.symbol, "AAPL.US")
        self.assertEqual(batch.status, DataStatus.HISTORICAL)
        self.assertEqual(batch.source, "stooq-daily-csv")
        self.assertEqual(len(batch.bars), 2)
        self.assertEqual(batch.bars[0].close, 103.0)
        self.assertEqual(batch.bars[-1].close, 105.0)
        self.assertTrue(batch.warnings)

    async def test_rejects_invalid_symbol_interval_and_limit(self):
        adapter = StooqAdapter()
        for args in [("", "1d", 5), ("AAPL.US", "1h", 5), ("AAPL.US", "1d", 0),
                     ("AAPL.US", "1d", 5001)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                await adapter.get_bars(*args)

    async def test_empty_csv_returns_clear_no_data_error(self):
        adapter = StooqAdapter()
        with patch.object(adapter, "_fetch_csv", return_value="Date,Open,High,Low,Close,Volume\n"):
            with self.assertRaisesRegex(ValueError, "No valid daily"):
                await adapter.get_bars("AAPL.US")

    async def test_quota_and_api_key_messages_are_not_parsed_as_data(self):
        for body, message in [
            ("Exceeded the daily hits limit", "quota"),
            ("Please provide APIKEY", "API key"),
            ("<html>blocked</html>", "non-CSV"),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(RuntimeError, message):
                StooqAdapter._parse_csv(body)

    async def test_malformed_rows_are_skipped(self):
        body = CSV + "bad-date,not-a-price,0,0,0,0\n"
        bars = StooqAdapter._parse_csv(body)
        self.assertEqual(len(bars), 3)

    def test_timeout_bounds(self):
        with self.assertRaises(ValueError):
            StooqAdapter(timeout_seconds=0.2)


if __name__ == "__main__":
    unittest.main()
