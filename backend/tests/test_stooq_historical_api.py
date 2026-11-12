import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.market_data import DataStatus, MarketDataBatch, OHLCVBar


class StooqHistoricalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "market.sqlite")})
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    @staticmethod
    def batch():
        return MarketDataBatch(
            symbol="AAPL.US", interval="1d", source="stooq-daily-csv",
            status=DataStatus.HISTORICAL, retrieved_at=datetime.now(timezone.utc),
            bars=[OHLCVBar(
                timestamp=datetime(2026, 10, 30, tzinfo=timezone.utc),
                open=100, high=105, low=99, close=103, volume=1000,
            )],
        )

    def test_endpoint_returns_and_persists_historical_data(self):
        with patch("app.main.StooqAdapter.get_bars", new_callable=AsyncMock, return_value=self.batch()) as fetch:
            response = self.client.get("/api/market-data/stooq", params={"symbol": "AAPL.US", "limit": 1})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "historical_research_ingestion")
        self.assertEqual(body["source"], "stooq-daily-csv")
        self.assertEqual(body["status"], "historical")
        self.assertEqual(body["observation_count"], 1)
        self.assertEqual(body["execution"], "disabled")
        self.assertIn("storage", body)
        fetch.assert_awaited_once_with("AAPL.US", "1d", 1)

    def test_endpoint_rejects_non_daily_interval_before_provider_call(self):
        with patch("app.main.StooqAdapter.get_bars", new_callable=AsyncMock) as fetch:
            response = self.client.get("/api/market-data/stooq", params={"symbol": "AAPL.US", "interval": "1h"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("daily interval", response.json()["detail"])
        fetch.assert_not_awaited()

    def test_endpoint_maps_provider_failure_to_502(self):
        with patch("app.main.StooqAdapter.get_bars", new_callable=AsyncMock, side_effect=RuntimeError("mock provider failure")):
            response = self.client.get("/api/market-data/stooq", params={"symbol": "AAPL.US"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("Historical provider unavailable", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()