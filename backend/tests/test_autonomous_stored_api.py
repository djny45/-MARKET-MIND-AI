import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

from app.market_data import MarketDataBatch
from app.market_store import store_batch
from app.main import autonomous_research_stored


class AutonomousStoredResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "market.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def add_batch(self, symbol="TEST", source="unit-test", status="historical", count=3):
        now = datetime(2026, 11, 3, tzinfo=timezone.utc)
        bars = []
        for index in range(count):
            price = 100 + index
            bars.append({
                "timestamp": now - timedelta(days=count - index),
                "open": price, "high": price + 2, "low": price - 2,
                "close": price + 1, "volume": 1000 + index,
            })
        batch = MarketDataBatch(
            symbol=symbol, interval="1d", source=source, status=status,
            retrieved_at=now, bars=bars,
        )
        store_batch(batch)

    async def call_endpoint(self, symbol="TEST", interval="1d", limit=500):
        return await autonomous_research_stored(symbol, interval, limit)

    def test_clean_stored_batch_returns_descriptive_report_and_provenance(self):
        import asyncio
        self.add_batch()
        result = asyncio.run(self.call_endpoint())
        self.assertEqual(result["mode"], "stored_descriptive_chart_research")
        self.assertEqual(result["source"], "unit-test")
        self.assertEqual(result["status"], "historical")
        self.assertEqual(result["observation_count"], 3)
        self.assertEqual(result["execution"], "disabled")
        self.assertIn("chart_report", result)

    def test_empty_or_single_bar_returns_404(self):
        import asyncio
        self.add_batch(count=1)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.call_endpoint())
        self.assertEqual(error.exception.status_code, 404)

    def test_mixed_sources_rejected(self):
        import asyncio
        self.add_batch(source="source-a")
        self.add_batch(source="source-b")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.call_endpoint())
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(error.exception.detail["error"], "mixed_or_missing_provenance")

    def test_mixed_statuses_rejected(self):
        import asyncio
        self.add_batch(status="historical")
        self.add_batch(source="unit-test-2", status="delayed")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.call_endpoint())
        self.assertEqual(error.exception.status_code, 409)

    def test_invalid_interval_rejected(self):
        import asyncio
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.call_endpoint(interval="weekly"))
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
