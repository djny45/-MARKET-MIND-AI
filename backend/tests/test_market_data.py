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

    def test_bar_rejects_infinite_ohlcv_values(self):
        for field in ("open", "high", "low", "close", "volume"):
            values = {
                "timestamp": "2026-01-01T00:00:00Z",
                "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
            }
            values[field] = float("inf")
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    OHLCVBar(**values)

    def test_bar_rejects_nan_ohlcv_values(self):
        for field in ("open", "high", "low", "close", "volume"):
            values = {
                "timestamp": "2026-01-01T00:00:00Z",
                "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
            }
            values[field] = float("nan")
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    OHLCVBar(**values)

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

    def test_batch_rejects_out_of_order_timestamps(self):
        older = {
            "timestamp": "2026-01-01T00:00:00Z",
            "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
        }
        newer = {
            "timestamp": "2026-01-02T00:00:00Z",
            "open": 11, "high": 13, "low": 10, "close": 12, "volume": 110,
        }
        base = {
            "symbol": "BTCUSD", "interval": "1d", "status": "historical",
            "source": "provider-x", "retrieved_at": "2026-01-03T00:00:00Z",
        }
        valid = MarketDataBatch(**base, bars=[older, newer])
        self.assertEqual(valid.bars[0].timestamp.isoformat(), "2026-01-01T00:00:00+00:00")
        with self.assertRaises(ValidationError):
            MarketDataBatch(**base, bars=[newer, older])

    def test_bar_rejects_low_above_high_even_when_open_and_close_are_lower(self):
        with self.assertRaises(ValidationError):
            OHLCVBar(
                timestamp="2026-01-01T00:00:00Z", open=8, high=9,
                low=10, close=8.5, volume=100,
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
