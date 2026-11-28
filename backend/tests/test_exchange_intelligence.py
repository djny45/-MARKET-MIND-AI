"""Tests for the integrated public-exchange intelligence extension."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.exchange_intelligence import (
    CAPABILITIES,
    capabilities_manifest,
    fear_greed_index,
    funding_open_interest,
    gold_token_quote,
    order_book_summary,
    venue_quote,
    venue_snapshot,
)
from app.market_data import DataStatus
from app.market_quotes import MarketQuote
from app.provider_adapters import ProviderError


class CapabilityTests(unittest.TestCase):
    def test_all_report_sources_have_capabilities(self):
        self.assertEqual(len(CAPABILITIES), 8)
        for name in ("okx-public", "coinbase-public", "bybit-public", "kraken-public",
                     "deribit-public", "hyperliquid-public", "alternative-sentiment",
                     "coingecko-gold-token"):
            self.assertIn(name, CAPABILITIES)

    def test_no_credentials_and_no_live_claim(self):
        manifest = capabilities_manifest()
        self.assertFalse(manifest["third_party_endpoints_used"])
        self.assertFalse(manifest["execution"]["broker_execution"])
        for adapter in manifest["adapters"]:
            self.assertTrue(adapter["requires_attestation"] or
                            adapter["name"] == "alternative-sentiment")

    def test_gold_is_labelled_tokenized_not_spot(self):
        cap = CAPABILITIES["coingecko-gold-token"]
        self.assertIn("tokenized_gold", cap.asset_classes)
        self.assertIn("not interchangeable with spot/futures gold", cap.limitations[0])


class VenueQuoteTests(unittest.TestCase):
    def test_okx_quote_uses_existing_contract_and_historical_status(self):
        payload = {"code": "0", "data": [{
            "instId": "BTC-USDT", "last": "60000.5",
            "bidPx": "60000", "askPx": "60001",
        }]}
        with patch("app.exchange_intelligence._fetch", return_value=payload):
            quote = venue_quote("okx", "BTCUSDT")
        self.assertIsInstance(quote, MarketQuote)
        self.assertEqual(quote.status, DataStatus.HISTORICAL)
        self.assertEqual(quote.last, 60000.5)
        self.assertEqual(quote.source, "okx-public")
        self.assertIsNone(quote.bid)  # quotes carry no executable bid/ask
        self.assertIsNone(quote.ask)

    def test_venue_failure_becomes_unavailable_with_reason(self):
        with patch("app.exchange_intelligence._fetch",
                   side_effect=ProviderError("okx-public returned HTTP 429 (Retry-After: 20s)")):
            quote = venue_quote("okx", "BTCUSDT")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIsNone(quote.last)
        self.assertIn("Retry-After", quote.reason or "")

    def test_unsupported_venue_is_unavailable(self):
        quote = venue_quote("mystery", "BTCUSDT")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)

    def test_coinbase_reference_rate_is_not_a_forex_quote(self):
        cap = CAPABILITIES["coinbase-public"]
        self.assertIn("reference_rate", cap.asset_classes)
        self.assertTrue(any("not an executable forex quote" in n for n in cap.limitations))


class DerivativesTests(unittest.TestCase):
    def test_funding_and_oi_keep_provider_timestamps(self):
        funding = {"data": [{
            "fundingRate": "0.0001", "fundingTime": "1795708800000",
        }]}
        oi = {"data": [{"oiUsd": "1929248672.77", "ts": "1795699532498"}]}
        with patch("app.exchange_intelligence._fetch", side_effect=[funding, oi]):
            row = funding_open_interest()
        self.assertEqual(row["status"], "historical")
        self.assertEqual(row["funding_rate"], 0.0001)
        self.assertEqual(row["open_interest_usd"], 1929248672.77)
        self.assertTrue(row["funding_time"].startswith("2026"))
        self.assertTrue(row["retrieved_at"].startswith("2026"))

    def test_depth_is_resting_orders_not_executed_trades(self):
        payload = {"data": [{
            "bids": [["100", "2"], ["99", "1"]],
            "asks": [["101", "3"], ["102", "1"]],
        }]}
        with patch("app.exchange_intelligence._fetch", return_value=payload):
            row = order_book_summary()
        self.assertAlmostEqual(row["bid_depth_usd"], 299.0)
        self.assertAlmostEqual(row["ask_depth_usd"], 405.0)
        self.assertIn("not executed trades", row["data_note"])

    def test_depth_failure_is_unavailable(self):
        with patch("app.exchange_intelligence._fetch", side_effect=ProviderError("HTTP 503")):
            row = order_book_summary()
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("reason", row)


class SentimentAndGoldTests(unittest.TestCase):
    def test_fear_greed_carries_value_classification_and_timestamp(self):
        payload = {"data": [{
            "value": "11", "value_classification": "Extreme Fear",
            "timestamp": "1795651200",
        }]}
        with patch("app.exchange_intelligence._fetch", return_value=payload):
            row = fear_greed_index()
        self.assertEqual(row["value"], 11)
        self.assertEqual(row["classification"], "Extreme Fear")
        self.assertTrue(row["timestamp"].startswith("2026"))
        self.assertEqual(row["status_label"], "HISTORICAL")

    def test_fear_greed_out_of_range_is_unavailable(self):
        with patch("app.exchange_intelligence._fetch",
                   return_value={"data": [{"value": "999", "timestamp": "1"}]}):
            row = fear_greed_index()
        self.assertEqual(row["status"], "unavailable")

    def test_gold_quote_uses_tokenized_source(self):
        payload = {"pax-gold": {"usd": 3559.46, "last_updated_at": 1795699551}}
        with patch("app.exchange_intelligence._fetch", return_value=payload):
            quote = gold_token_quote()
        self.assertEqual(quote.source, "coingecko-gold-token")
        self.assertEqual(quote.symbol, "PAXG")
        self.assertEqual(quote.status, DataStatus.HISTORICAL)
        self.assertEqual(quote.timestamp.tzinfo, timezone.utc)

    def test_gold_unavailable_has_no_price(self):
        with patch("app.exchange_intelligence._fetch", side_effect=ProviderError("HTTP 429")):
            quote = gold_token_quote()
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIsNone(quote.last)


if __name__ == "__main__":
    unittest.main()
