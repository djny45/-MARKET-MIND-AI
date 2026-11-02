import unittest
from datetime import datetime

from pydantic import ValidationError

from app.market_data import (
    DataStatus,
    MarketDataBatch,
    OHLCVBar,
    SyntheticFixtureAdapter,
)


class MarketDataContractTests(unittest.TestCase):
    def test_bar_requires_timezone_aware_timestamp(self):
        with self.assertRaises(ValidationError):
            OHLCVBar(
                timestamp=datetime(2026, 1, 1), open=10, high=12,
                low=9, close=11, volume=100,
            )

    def test_bar_rejects_infinite_price_and_nan_volume(self):
        for values in (
            {"open": float("inf"), "high": 12, "low": 9, "close": 11, "volume": 100},
            {"open": 10, "high": 12, "low": 9, "close": 11, "volume": float("nan")},
            {"open": 10, "high": float("-inf"), "low": 9, "close": 11, "volume": 100},
            {"open": 10, "high": 12, "low": 9, "close": 11, "volume": float("inf")},
        ):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValidationError, "finite"):
                    OHLCVBar(timestamp="2026-01-01T00:00:00Z", **values)

    def test_bar_rejects_invalid_ohlc_range(self):
        with self.assertRaises(ValidationError):
            OHLCVBar(
                timestamp="2026-01-01T00:00:00Z", open=10, high=8,
                low=9, close=11, volume=100,
            )

    def test_batch_normalizes_symbol_and_rejects_unknown_interval(self):
        batch = MarketDataBatch(
            symbol=" btcusd ", interval="1h", status="historical",
            source="provider-x", retrieved_at="2026-01-01T00:00:00Z",
            bars=[],
        )
        self.assertEqual(batch.symbol, "BTCUSD")
        with self.assertRaises(ValidationError):
            MarketDataBatch(
                symbol="BTCUSD", interval="5m", status="historical",
                source="provider-x", retrieved_at="2026-01-01T00:00:00Z",
                bars=[],
            )

    def test_batch_rejects_duplicate_timestamps(self):
        bar = {
            "timestamp": "2026-01-01T00:00:00Z",
            "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
        }
        with self.assertRaises(ValidationError):
            MarketDataBatch(
                symbol="BTCUSD", interval="1d", status="historical",
                source="provider-x", retrieved_at="2026-01-02T00:00:00Z",
                bars=[bar, bar],
            )

    def test_bar_rejects_low_above_high_even_when_open_and_close_are_lower(self):
        with self.assertRaises(ValidationError):
            OHLCVBar(
                timestamp="2026-01-01T00:00:00Z", open=8, high=9,
                low=10, close=8.5, volume=100,
            )

    def test_batch_rejects_out_of_order_timestamps(self):
        first = {
            "timestamp": "2026-01-02T00:00:00Z",
            "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
        }
        second = {
            "timestamp": "2026-01-01T00:00:00Z",
            "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
        }
        with self.assertRaisesRegex(ValidationError, "ascending timestamp"):
            MarketDataBatch(
                symbol="BTCUSD", interval="1d", status="historical",
                source="provider-x", retrieved_at="2026-01-03T00:00:00Z",
                bars=[first, second],
            )

    def test_batch_rejects_unlabelled_extra_fields(self):
        with self.assertRaises(ValidationError):
            MarketDataBatch(
                symbol="TEST", interval="1d", status="synthetic",
                source="fixture", retrieved_at="2026-01-01T00:00:00Z",
                bars=[], provider_secret="must-not-be-accepted",
            )


class SyntheticFixtureAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixture_is_explicitly_synthetic_and_deterministic(self):
        adapter = SyntheticFixtureAdapter()
        first = await adapter.get_bars("btcusd", "1d", 3)
        second = await adapter.get_bars("BTCUSD", "1d", 3)
        self.assertEqual(first.status, DataStatus.SYNTHETIC)
        self.assertEqual(first.source, "synthetic-fixture")
        self.assertEqual([bar.close for bar in first.bars], [bar.close for bar in second.bars])
        self.assertEqual(first.symbol, "BTCUSD")
        self.assertTrue(first.warnings)

    async def test_fixture_rejects_unsupported_interval_and_limit(self):
        adapter = SyntheticFixtureAdapter()
        with self.assertRaises(ValueError):
            await adapter.get_bars("BTCUSD", "5m", 5)
        with self.assertRaises(ValueError):
            await adapter.get_bars("BTCUSD", "1d", 6)


if __name__ == "__main__":
    unittest.main()
