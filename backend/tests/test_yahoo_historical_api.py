import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.market_data import DataStatus, MarketDataBatch, OHLCVBar


class YahooHistoricalApiTests(unittest.TestCase):
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
        retrieved = datetime.now(timezone.utc)
        return MarketDataBatch(
            symbol="AAPL",
            interval="1d",
            source="yahoo-finance-chart",
            status=DataStatus.HISTORICAL,
            retrieved_at=retrieved,
            bars=[
                OHLCVBar(
                    timestamp=datetime(2026, 10, 30, tzinfo=timezone.utc),
                    open=100, high=105, low=99, close=103, volume=1000,
                ),
                OHLCVBar(
                    timestamp=datetime(2026, 10, 31, tzinfo=timezone.utc),
                    open=103, high=107, low=102, close=106, volume=1200,
                ),
            ],
        )

    def test_endpoint_returns_and_persists_historical_provenance(self):
        with patch("app.main.YahooFinanceAdapter.get_bars", return_value=self.batch()) as fetch:
            response = self.client.get("/api/market-data/yahoo", params={"symbol": "AAPL", "interval": "1d", "limit": 2})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "historical_research_ingestion")
        self.assertEqual(body["source"], "yahoo-finance-chart")
        self.assertEqual(body["status"], "historical")
        self.assertEqual(body["observation_count"], 2)
        self.assertEqual(body["execution"], "disabled")
        self.assertEqual(len(body["bars"]), 2)
        self.assertIn("storage", body)
        fetch.assert_called_once_with("AAPL", "1d", 2)

    def test_invalid_query_parameters_return_400_before_provider_call(self):
        cases = [
            ({"symbol": ""}, "symbol"),
            ({"symbol": "AAPL", "interval": "2m"}, "interval"),
            ({"symbol": "AAPL", "limit": 0}, "limit"),
            ({"symbol": "AAPL", "limit": 5001}, "limit"),
        ]
        with patch("app.main.YahooFinanceAdapter.get_bars") as fetch:
            for params, expected in cases:
                response = self.client.get("/api/market-data/yahoo", params=params)
                self.assertEqual(response.status_code, 400, params)
                self.assertIn(expected, response.json()["detail"])
            fetch.assert_not_called()

    def test_provider_status_distinguishes_historical_from_live(self):
        response = self.client.get("/api/providers/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "no_live_provider_configured")
        self.assertEqual(body["live_providers"], [])
        self.assertEqual(body["historical_providers"][0]["name"], "yahoo-finance-chart")
        self.assertEqual(body["historical_providers"][0]["status"], "implemented_not_probed")
        self.assertEqual(body["historical_providers"][0]["data_status"], "historical")
        self.assertEqual(body["historical_providers"][1]["name"], "stooq-daily-csv")
        self.assertEqual(body["historical_providers"][1]["endpoint"], "/api/market-data/stooq")
        self.assertEqual(body["available_adapters"][0]["data_status"], "synthetic")

    def test_provider_failure_maps_to_502_without_live_network(self):
        with patch("app.main.YahooFinanceAdapter.get_bars", side_effect=RuntimeError("mock provider failure")):
            response = self.client.get("/api/market-data/yahoo", params={"symbol": "AAPL"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("Historical provider unavailable", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
