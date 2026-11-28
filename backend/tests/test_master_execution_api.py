"""API contract tests for master-execution endpoints (bounded/offline)."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/master-api.db"
from fastapi.testclient import TestClient
from app.main import app
from app.provider_adapters import ProviderError


class MasterApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_instrument_search_finds_derivative_contracts(self):
        for symbol in ("BTC-USDT-SWAP", "XAU-USDT-SWAP", "PAXG-USDT"):
            response = self.client.get("/api/instruments", params={"q": symbol})
            self.assertEqual(response.status_code, 200)
            rows = response.json()["instruments"]
            self.assertTrue(any(row["symbol"] == symbol for row in rows), symbol)
            self.assertTrue(any(row.get("contract_class") for row in rows))

    def test_relay_manifest_is_fixed_allowlist(self):
        body = self.client.get("/api/intelligence/relay/manifest").json()
        self.assertFalse(body["accepts_caller_url"])
        self.assertFalse(body["credentials_forwarded"])
        self.assertIn("/api/v5/market/ticker", body["allowed_paths"])

    def test_relay_rejects_unallowlisted_path(self):
        response = self.client.get("/api/intelligence/relay/okx",
                                   params={"path": "https://evil.example"})
        self.assertEqual(response.status_code, 400)

    def test_llm_health_is_safe_without_configuration(self):
        response = self.client.get("/api/intelligence-core/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["status"], {"not_configured", "healthy", "degraded"})
        self.assertFalse(body["network_called"])

    def test_order_book_replay_reports_no_book_without_events(self):
        response = self.client.get("/api/intelligence/order-book/replay")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["replay"]["valid"])
        self.assertIn("gap", body["replay"]["status"])

    def test_okx_market_structure_is_provenance_tagged(self):
        with patch("app.exchange_intelligence._fetch",
                   side_effect=ProviderError("okx-public returned HTTP 503")):
            body = self.client.get("/api/intelligence/okx/market-structure").json()
        for key in ("mark_price", "funding_history", "liquidations", "candles"):
            self.assertEqual(body[key]["status"], "unavailable")
            self.assertIn("reason", body[key])
        self.assertTrue(body["unavailable_endpoints"])

    def test_deribit_and_fx_views_are_available(self):
        self.assertEqual(
            self.client.get("/api/intelligence/deribit/options").status_code, 200
        )
        fx = self.client.get("/api/intelligence/fx/reference").json()
        self.assertIn(fx["status"], {"reference", "unavailable"})
        self.assertIn("not an executable forex quote", fx["note"])

    def test_research_topics_still_use_existing_skills(self):
        body = self.client.get("/api/intelligence/research/topics").json()
        self.assertFalse(body["new_agents_created"])
        self.assertFalse(body["new_skills_created"])
        self.assertEqual(len(body["topics"]), 8)


if __name__ == "__main__":
    unittest.main()
