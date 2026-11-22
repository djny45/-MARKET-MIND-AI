import unittest
import time
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class MarketMakingResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.auth_patch = patch.dict(os.environ, {"API_AUTH_REQUIRED": "false"})
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.client = TestClient(app)
        self.now = time.time()

    def payload(self, *, bid=99, ask=101, timestamp=None, **extra):
        return {
            "bid": bid,
            "ask": ask,
            "timestamp": self.now if timestamp is None else timestamp,
            **extra,
        }

    def test_endpoint_returns_indicative_research_only_quote(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json=self.payload(inventory=1, inventory_skew_bps_per_unit=5),
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "research_only_indicative_quotes")
        self.assertFalse(payload["broker_execution"])
        self.assertFalse(payload["orders_submitted"])
        self.assertAlmostEqual(payload["mid_price"], 100)

    def test_endpoint_rejects_stale_book(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json=self.payload(timestamp=self.now - 120),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("stale", response.json()["detail"])

    def test_endpoint_rejects_crossed_book(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json=self.payload(bid=102, ask=101),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("crossed", response.json()["detail"])

    def test_endpoint_bounds_parameters(self):
        response = self.client.post(
            "/api/research/market-making/indicative",
            json=self.payload(max_age_seconds=10000),
        )
        self.assertEqual(response.status_code, 422)



if __name__ == "__main__":
    unittest.main()
