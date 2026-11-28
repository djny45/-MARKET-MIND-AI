"""Tests for master-execution extensions: instruments, relay, flow, LLM health."""
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/master.db"

from app import exchange_relay, intelligence_core, trade_flow
from app.instruments import INSTRUMENTS
from app.instrument_master import sync_reference_catalogue, search_instrument_master
from app.market_event_quality import diagnose_event_fields, diagnose_event_staleness
from app.market_events import store_market_events


class InstrumentExtensionTests(unittest.TestCase):
    def test_all_requested_symbols_exist(self):
        symbols = {i["symbol"] for i in INSTRUMENTS}
        for symbol in ("BTC-USDT-SWAP", "BTC-USDT", "ETH-USDT-SWAP", "ETH-USDT",
                       "XAU-USDT-SWAP", "XAUT-USDT", "PAXG-USDT"):
            self.assertIn(symbol, symbols)

    def test_contract_classes_distinguish_instruments(self):
        by_symbol = {i["symbol"]: i for i in INSTRUMENTS}
        self.assertIn("derivative", by_symbol["BTC-USDT-SWAP"]["contract_class"])
        self.assertIn("token", by_symbol["PAXG-USDT"]["contract_class"])
        self.assertIn("spot", by_symbol["XAUUSD"]["contract_class"])

    def test_persistent_registry_seeds_contract_class(self):
        sync_reference_catalogue()
        row = search_instrument_master(query="XAU-USDT-SWAP")["instruments"][0]
        self.assertIn("commodity derivative", row["contract_class"])


class RelaySecurityTests(unittest.TestCase):
    def test_only_fixed_allowlisted_paths_and_params(self):
        with self.assertRaises(exchange_relay.RelayPolicyError):
            exchange_relay.validate_relay_request("https://evil.example", {})
        with self.assertRaises(exchange_relay.RelayPolicyError):
            exchange_relay.validate_relay_request("/api/v5/market/ticker", {"url": "http://evil"})
        with self.assertRaises(exchange_relay.RelayPolicyError):
            exchange_relay.validate_relay_request("/api/v5/market/ticker", {"instId": "bad url"})
        url, _ = exchange_relay.validate_relay_request(
            "/api/v5/market/ticker", {"instId": "BTC-USDT"}
        )
        self.assertTrue(url.startswith("https://www.okx.com/api/v5/market/ticker?"))

    def test_manifest_declares_no_caller_url_or_credentials(self):
        m = exchange_relay.manifest()
        self.assertFalse(m["accepts_caller_url"])
        self.assertFalse(m["credentials_forwarded"])
        self.assertFalse(m["tredye_endpoints_used"])

    def test_relay_failure_is_unavailable(self):
        with patch("app.exchange_relay._raw_fetch",
                   side_effect=exchange_relay.ProviderError("okx-relay returned HTTP 429")):
            row = exchange_relay.relay("/api/v5/market/ticker", {"instId": "BTC-USDT"})
        self.assertEqual(row["status"], "unavailable")
        self.assertFalse(row["credentials_forwarded"])


class FlowExtensionTests(unittest.TestCase):
    def test_taker_volume_from_known_sides_only(self):
        events = [
            {"event_type": "trade", "payload": {"price": 100, "quantity": 2, "side": "buy"}},
            {"event_type": "trade", "payload": {"price": 100, "quantity": 1, "side": "sell"}},
            {"event_type": "trade", "payload": {"price": 100, "quantity": 1, "side": "unknown"}},
        ]
        row = trade_flow.build_taker_volume_summary(events)
        self.assertEqual(row["taker_buy_notional"], 200.0)
        self.assertEqual(row["taker_sell_notional"], 100.0)
        self.assertEqual(row["unknown_side_count"], 1)

    def test_long_short_ratio_requires_supplied_observations(self):
        result = trade_flow.build_long_short_ratio([])
        self.assertFalse(result["available"])
        result = trade_flow.build_long_short_ratio([{
            "event_type": "ratio", "event_time": "2026-01-01T00:00:00Z",
            "payload": {"long_ratio": 60, "short_ratio": 40},
        }])
        self.assertTrue(result["available"])
        self.assertEqual(result["observations"][0]["ratio"], 1.5)

    def test_basis_requires_time_aligned_prices(self):
        spot = [{"event_time": "t1", "payload": {"price": 100}}]
        perp = [{"event_time": "t1", "payload": {"mark_price": 102}}]
        result = trade_flow.build_basis_summary(perp, spot)
        self.assertTrue(result["available"])
        self.assertEqual(result["observations"][0]["basis"], 2.0)
        self.assertFalse(trade_flow.build_basis_summary(
            [{"event_time": "t2", "payload": {"mark_price": 102}}], spot
        )["available"])


class EventQualityExtensionTests(unittest.TestCase):
    def test_missing_fields_reported(self):
        result = diagnose_event_fields([{"event_type": "trade", "payload": {}}])
        self.assertGreater(result["missing_field_count"], 0)
        self.assertTrue(any(item["field"] == "payload.price" for item in result["missing_fields"]))

    def test_stale_event_reported(self):
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        result = diagnose_event_staleness([{
            "event_time": old, "status": "live",
        }])
        self.assertEqual(result["stale_count"], 1)

    def test_unlabelled_status_is_reported_not_assumed(self):
        result = diagnose_event_staleness([{"event_time": "2026-01-01T00:00:00Z", "status": ""}])
        self.assertEqual(result["unlabelled_count"], 1)


class LlmReliabilityTests(unittest.TestCase):
    def test_health_without_configuration_makes_no_network_call(self):
        with patch("app.intelligence_core.intelligence_core_status",
                   return_value={"provider": "none", "configured": False}), \
             patch("app.intelligence_core.synthesize_research") as synth:
            result = intelligence_core.check_provider_health()
        self.assertEqual(result["status"], "not_configured")
        self.assertFalse(result["network_called"])
        synth.assert_not_called()

    def test_health_reports_degraded_on_provider_failure(self):
        with patch("app.intelligence_core.intelligence_core_status",
                   return_value={"provider": "mercury", "configured": True}), \
             patch("app.intelligence_core.synthesize_research",
                   return_value={"status": "provider_unavailable", "attempts": 2}):
            result = intelligence_core.check_provider_health()
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(result["network_called"])
        self.assertEqual(result["attempts"], 2)

    def test_retry_bounded_on_transport_error(self):
        calls = []
        def failing_opener(_request, timeout=None):
            calls.append(timeout)
            raise URLError("offline")

        with patch.dict(os.environ, {
            "INTELLIGENCE_CORE_ENABLED": "true",
            "INTELLIGENCE_CORE_PROVIDER": "mercury",
            "INCEPTION_API_KEY": "test-key-not-a-secret",
        }), patch("app.intelligence_core.time.sleep"):
            result = intelligence_core.synthesize_research(
                {"test": "retry"}, opener=failing_opener
            )
        self.assertEqual(result["status"], "provider_unavailable")
        self.assertLessEqual(len(calls), intelligence_core.DEFAULT_RETRIES + 1)
        self.assertIn("bounded", result["reason"])
        self.assertTrue(all(t == intelligence_core.DEFAULT_TIMEOUT_SECONDS for t in calls))


if __name__ == "__main__":
    unittest.main()
