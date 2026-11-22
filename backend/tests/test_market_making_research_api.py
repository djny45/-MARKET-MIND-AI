import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


class MarketMakingResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.now = datetime.now(timezone.utc)

    def snapshot(self, *, bid="99", ask="101", timestamp=None):
        return {
            "best_bid": bid,
            "best_ask": ask,
            "timestamp": (timestamp or self.now).isoformat(),
        }

    def test_endpoint_returns_indicative_research_only_quote(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json={"snapshot": self.snapshot(), "inventory": 1, "inventory_skew_bps": 5},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "research_only_indicative")
        self.assertEqual(payload["mid"], "100")
        self.assertIn("limitations", payload)

    def test_endpoint_rejects_stale_book(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json={"snapshot": self.snapshot(timestamp=self.now - timedelta(minutes=2))},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("stale", response.json()["detail"])

    def test_endpoint_rejects_crossed_book(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json={"snapshot": self.snapshot(bid="102", ask="101")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("crossed", response.json()["detail"])

    def test_endpoint_bounds_parameters(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json={"snapshot": self.snapshot(), "max_age_seconds": 10000},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
