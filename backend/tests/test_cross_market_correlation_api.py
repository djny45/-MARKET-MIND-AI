import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from app.main import cross_market_correlation
from app.market_data import MarketDataBatch, OHLCVBar, DataStatus
from app import market_store


class CrossMarketCorrelationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "correlation.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def store(self, symbol, closes):
        bars = []
        for index, close in enumerate(closes, start=1):
            bars.append(OHLCVBar(
                timestamp=f"2026-01-{index:02d}T00:00:00+00:00",
                open=close, high=close + 1, low=close - 1,
                close=close, volume=100,
            ))
        batch = MarketDataBatch(
            symbol=symbol, interval="1d", status=DataStatus.HISTORICAL,
            source="unit-test-import", retrieved_at="2026-02-01T00:00:00+00:00",
            bars=bars,
        )
        market_store.store_batch(batch)

    def test_api_returns_pairwise_historical_correlation(self):
        self.store("INDIA_A", [100, 110, 99, 108.9])
        self.store("US_B", [50, 55, 49.5, 54.45])
        result = cross_market_correlation("INDIA_A,US_B", "1d", 100, 3)
        self.assertEqual(result["pairs"][0]["status"], "available")
        self.assertAlmostEqual(result["pairs"][0]["correlation"], 1.0)
        self.assertEqual(result["execution"], "disabled")

    def test_api_rejects_invalid_symbol_count(self):
        with self.assertRaises(HTTPException) as error:
            cross_market_correlation("INDIA_A", "1d", 100, 3)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
