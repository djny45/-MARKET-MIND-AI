"""API contract tests for the four-market terminal endpoints.

The adapters are patched to fail, so these run offline and assert the HTTP
behaviour: status codes, attribution fields, label discipline and the
execution boundary.
"""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import four_market_terminal
from app.main import app
from app.provider_adapters import ProviderError

ISO = "2026-11-26T12:00:00Z"


def _offline():
    """Patch every adapter so no test reaches the network."""
    return [
        patch("app.provider_adapters.UsEquitiesAdapter._get_json",
              side_effect=ProviderError("offline")),
        patch("app.provider_adapters.IndiaEquitiesAdapter._get_json",
              side_effect=ProviderError("offline")),
        patch("app.provider_adapters.EcbForexAdapter._get",
              side_effect=ProviderError("offline")),
        patch("app.provider_adapters.CoinGeckoCryptoAdapter._get_json",
              side_effect=ProviderError("offline")),
    ]


class FourMarketTerminalApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": str(Path(self.tmp.name) / "terminal.db"),
        })
        self.env.start()
        four_market_terminal.clear_cache()
        self.patchers = _offline()
        for patcher in self.patchers:
            patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
        self.env.stop()
        self.tmp.cleanup()
        four_market_terminal.clear_cache()

    def test_board_returns_four_markets_with_attribution(self):
        response = self.client.get("/api/terminal/four-market?refresh=true")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "four_market_research_terminal")
        self.assertEqual(
            [m["market_group"] for m in body["markets"]],
            ["us", "india", "forex", "crypto"],
        )
        for market in body["markets"]:
            self.assertTrue(market["adapter"]["name"])
            self.assertIn("market_status", market)
            for quote in market["quotes"]:
                self.assertTrue(quote["source"])
                self.assertIn(quote["status"], {
                    "live", "delayed", "historical", "synthetic", "unavailable",
                })
                self.assertEqual(quote["status_label"], quote["status"].upper())
                self.assertIn("timestamp", quote)
                self.assertIn("retrieved_at", quote)

    def test_offline_board_never_invents_a_price(self):
        body = self.client.get("/api/terminal/four-market?refresh=true").json()
        for market in body["markets"]:
            for quote in market["quotes"]:
                self.assertEqual(quote["status"], "unavailable")
                self.assertIsNone(quote["last"])
                self.assertTrue(quote["reason"])
        self.assertEqual(body["totals"]["usable"], 0)

    def test_board_reports_execution_boundary(self):
        body = self.client.get("/api/terminal/four-market").json()
        self.assertFalse(body["execution"]["broker_execution"])
        self.assertFalse(body["execution"]["real_money"])
        self.assertFalse(body["execution"]["paper_trading"])

    def test_market_filter_is_honoured(self):
        body = self.client.get("/api/terminal/four-market?markets=india,us&refresh=true").json()
        self.assertEqual([m["market_group"] for m in body["markets"]], ["india", "us"])

    def test_invalid_market_filter_is_a_400(self):
        response = self.client.get("/api/terminal/four-market?markets=mars")
        self.assertEqual(response.status_code, 400)
        self.assertIn("markets must be", response.json()["detail"])

    def test_symbol_filter_requires_market_prefix(self):
        response = self.client.get("/api/terminal/four-market?symbols=AAPL")
        self.assertEqual(response.status_code, 400)
        self.assertIn("market:SYMBOL", response.json()["detail"])

    def test_symbol_filter_limits_requested_rows(self):
        body = self.client.get(
            "/api/terminal/four-market?symbols=us:AAPL&refresh=true"
        ).json()
        us = next(m for m in body["markets"] if m["market_group"] == "us")
        self.assertEqual([q["symbol"] for q in us["quotes"]], ["AAPL"])

    def test_symbol_filter_rejects_oversized_request(self):
        symbols = ",".join(f"us:SYM{i}" for i in range(41))
        response = self.client.get(f"/api/terminal/four-market?symbols={symbols}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 40", response.json()["detail"])

    def test_summary_endpoint_matches_board(self):
        board = self.client.get("/api/terminal/four-market?refresh=true").json()
        summary = self.client.get("/api/terminal/four-market/summary").json()
        self.assertEqual(len(summary["markets"]), len(board["markets"]))
        self.assertEqual(summary["totals"]["quotes"], board["totals"]["quotes"])

    def test_provider_endpoint_exposes_legend_and_capabilities(self):
        body = self.client.get("/api/terminal/providers").json()
        self.assertEqual(body["market_groups"], ["india", "us", "crypto", "forex"])
        self.assertFalse(body["credentials_required"])
        self.assertTrue(body["providers"]["live_claims_require_attestation"])
        labels = {item["label"] for item in body["legend"]["labels"]}
        self.assertEqual(
            labels, {"LIVE", "DELAYED", "HISTORICAL", "SYNTHETIC", "UNAVAILABLE"}
        )

    def test_attested_source_can_reach_delayed_label(self):
        """An attested adapter is the only route to a non-historical label."""
        observed = datetime(2026, 11, 26, 11, 59, tzinfo=timezone.utc)
        from app.market_quotes import MarketQuote
        quote = MarketQuote(
            symbol="AAPL", name="Apple Inc.", asset_class="equities",
            market_group="us", exchange="NASDAQ", currency="USD",
            last=200.0, timestamp=observed, retrieved_at=observed,
            status="delayed", source="yahoo-us-equities",
            attested_sources=frozenset({"yahoo-us-equities"}),
        )
        with patch.dict(os.environ, {
            "MARKET_MIND_ATTESTED_DATA_SOURCES": "yahoo-us-equities",
        }), patch("app.four_market_terminal.quotes_for_instruments",
                  return_value=[quote]):
            four_market_terminal.clear_cache()
            body = self.client.get(
                "/api/terminal/four-market?symbols=us:AAPL&refresh=true"
            ).json()
        us = next(m for m in body["markets"] if m["market_group"] == "us")
        self.assertEqual(us["quotes"][0]["status"], "delayed")
        self.assertEqual(body["attested_sources"], ["yahoo-us-equities"])

    def test_providers_status_lists_the_four_adapters(self):
        body = self.client.get("/api/providers/status").json()
        names = {item["name"] for item in body["available_adapters"]}
        self.assertIn("yahoo-us-equities", names)
        self.assertIn("yahoo-india-nse-bse", names)
        self.assertIn("ecb-reference-rates", names)
        self.assertIn("coingecko-public", names)


if __name__ == "__main__":
    unittest.main()
