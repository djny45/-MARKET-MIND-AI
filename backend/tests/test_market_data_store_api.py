"""Store endpoint must reject unattested live/delayed status claims."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def batch(status: str, source: str) -> dict:
    return {
        "symbol": "AAPL", "interval": "1d", "status": status, "source": source,
        "retrieved_at": "2026-01-01T00:00:00Z", "bars": [],
    }


class MarketDataStoreApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": str(Path(self.tmp.name) / "store.db")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_live_claim_from_unattested_source_is_rejected(self):
        response = TestClient(app).post("/api/market-data/store", json=batch("live", "customer-csv"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("not attested", response.json()["detail"])

    def test_historical_claim_is_accepted(self):
        response = TestClient(app).post(
            "/api/market-data/store", json=batch("historical", "manual-review")
        )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
