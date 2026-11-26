"""Tests for the four-market provider adapters.

Network is never touched: each adapter's single HTTP seam is patched. The
assertions focus on the safety properties that matter for a research terminal:
attribution, timestamps, honest status labels and the no-fabricated-price rule.
"""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.market_data import DataStatus
from app.market_quotes import MarketQuote
from app.provider_adapters import (
    ADAPTERS,
    CoinGeckoCryptoAdapter,
    EcbForexAdapter,
    IndiaEquitiesAdapter,
    ProviderError,
    UsEquitiesAdapter,
    adapter_manifest,
    adapters_for,
    quotes_for_instruments,
)


def _yahoo_payload(closes, stamps=None):
    stamps = stamps or [
        int(datetime(2026, 11, 20, tzinfo=timezone.utc).timestamp()) + i * 86400
        for i in range(len(closes))
    ]
    return {
        "chart": {
            "error": None,
            "result": [{
                "timestamp": stamps,
                "meta": {"exchangeTimezoneName": "America/New_York", "currency": "USD"},
                "indicators": {"quote": [{
                    "open": list(closes), "high": list(closes),
                    "low": list(closes), "close": list(closes),
                    "volume": [1000] * len(closes),
                }]},
            }],
        },
    }


ECB_CSV = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE
EXR,D,USD,EUR,SP00,A,2026-11-24,1.05
EXR,D,USD,EUR,SP00,A,2026-11-25,1.10
"""


class AdapterManifestTests(unittest.TestCase):
    def test_exactly_one_adapter_per_market_group(self):
        manifest = adapter_manifest()
        self.assertEqual(manifest["market_groups"], ["us", "india", "forex", "crypto"])
        groups = [item["market_group"] for item in manifest["adapters"]]
        self.assertEqual(sorted(groups), ["crypto", "forex", "india", "us"])
        self.assertEqual(len(groups), len(set(groups)))

    def test_manifest_claims_no_credentials_and_requires_attestation(self):
        manifest = adapter_manifest()
        self.assertFalse(manifest["credentials_required"])
        self.assertFalse(manifest["credentials_exposed"])
        self.assertTrue(manifest["live_claims_require_attestation"])
        for adapter in manifest["adapters"]:
            self.assertFalse(adapter["credentials_required"])

    def test_unknown_market_group_is_rejected(self):
        with self.assertRaises(ValueError):
            adapters_for("mars")


class StatusResolutionTests(unittest.TestCase):
    def test_unattested_source_degrades_to_historical(self):
        adapter = UsEquitiesAdapter()
        self.assertEqual(
            adapter.resolve_status([]), DataStatus.HISTORICAL
        )

    def test_attested_source_may_claim_preferred_status(self):
        adapter = UsEquitiesAdapter()
        self.assertEqual(
            adapter.resolve_status(["yahoo-us-equities"]), DataStatus.DELAYED
        )

    def test_attestation_is_case_insensitive_and_exact(self):
        adapter = UsEquitiesAdapter()
        self.assertEqual(
            adapter.resolve_status(["  Yahoo-US-Equities "]), DataStatus.DELAYED
        )
        # A near-miss must not grant the label.
        self.assertEqual(
            adapter.resolve_status(["yahoo-us"]), DataStatus.HISTORICAL
        )

    def test_adapter_without_attestation_requirement_keeps_its_label(self):
        adapter = EcbForexAdapter()
        self.assertEqual(
            adapter.resolve_status([]), DataStatus.HISTORICAL
        )


class UsEquitiesAdapterTests(unittest.TestCase):
    def test_maps_us_symbols_to_provider_conventions(self):
        adapter = UsEquitiesAdapter()
        self.assertEqual(adapter.provider_symbol("AAPL"), "AAPL")
        self.assertEqual(adapter.provider_symbol("spx"), "^GSPC")

    def test_successful_fetch_is_labelled_historical_without_attestation(self):
        adapter = UsEquitiesAdapter()
        with patch.object(adapter, "_get_json", return_value=_yahoo_payload([100.0, 103.0])):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        self.assertIsInstance(quote, MarketQuote)
        self.assertEqual(quote.status, DataStatus.HISTORICAL)
        self.assertEqual(quote.status_label, "HISTORICAL")
        self.assertEqual(quote.last, 103.0)
        self.assertEqual(quote.source, "yahoo-us-equities")
        self.assertEqual(quote.market_group, "us")
        self.assertEqual(quote.change_pct, 3.0)
        self.assertEqual(quote.timestamp.tzinfo, timezone.utc)
        self.assertGreaterEqual(quote.retrieved_at, quote.timestamp)

    def test_attested_fetch_is_labelled_delayed(self):
        adapter = UsEquitiesAdapter()
        with patch.object(adapter, "_get_json", return_value=_yahoo_payload([100.0, 103.0])):
            quote = adapter.fetch_quote(
                symbol="AAPL", name="Apple Inc.",
                attested_sources=["yahoo-us-equities"],
            )
        self.assertEqual(quote.status, DataStatus.DELAYED)

    def test_transport_failure_returns_unavailable_not_a_price(self):
        adapter = UsEquitiesAdapter()
        with patch.object(adapter, "_get_json", side_effect=ProviderError("upstream 503")):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIsNone(quote.last)
        self.assertIn("503", quote.reason)
        self.assertEqual(quote.source, "yahoo-us-equities")

    def test_empty_close_series_returns_unavailable(self):
        adapter = UsEquitiesAdapter()
        payload = {"chart": {"error": None, "result": [{
            "timestamp": [], "indicators": {"quote": [{"close": []}]}}]}}
        with patch.object(adapter, "_get_json", return_value=payload):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIsNone(quote.last)

    def test_non_finite_and_negative_closes_are_skipped(self):
        adapter = UsEquitiesAdapter()
        payload = _yahoo_payload([100.0, float("nan"), -5.0, 104.0])
        with patch.object(adapter, "_get_json", return_value=payload):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        self.assertEqual(quote.last, 104.0)


class IndiaEquitiesAdapterTests(unittest.TestCase):
    def test_suffixes_nse_and_bse_symbols(self):
        adapter = IndiaEquitiesAdapter()
        self.assertEqual(adapter.provider_symbol("RELIANCE", "NSE"), "RELIANCE.NS")
        self.assertEqual(adapter.provider_symbol("RELIANCE", "BSE"), "RELIANCE.BO")
        self.assertEqual(adapter.provider_symbol("NIFTY50"), "^NSEI")
        self.assertEqual(adapter.provider_symbol("SENSEX"), "^BSESN")

    def test_india_quote_keeps_inr_and_nse_exchange(self):
        adapter = IndiaEquitiesAdapter()
        with patch.object(adapter, "_get_json", return_value=_yahoo_payload([1400.0, 1450.5])):
            quote = adapter.fetch_quote(
                symbol="RELIANCE", name="Reliance Industries Ltd.",
                exchange="NSE", currency="INR",
            )
        self.assertEqual(quote.market_group, "india")
        self.assertEqual(quote.currency, "INR")
        self.assertEqual(quote.exchange, "NSE")
        self.assertEqual(quote.last, 1450.5)
        self.assertEqual(quote.status, DataStatus.HISTORICAL)

    def test_india_failure_is_unavailable_with_reason(self):
        adapter = IndiaEquitiesAdapter()
        with patch.object(adapter, "_get_json", side_effect=ProviderError("HTTP 404")):
            quote = adapter.fetch_quote(symbol="RELIANCE", name="Reliance Industries Ltd.")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertEqual(quote.market_group, "india")


class EcbForexAdapterTests(unittest.TestCase):
    def test_direct_pair_uses_ecb_rate_and_reference_date(self):
        adapter = EcbForexAdapter()
        with patch.object(adapter, "_get", return_value=ECB_CSV):
            quote = adapter.fetch_quote(symbol="EURUSD", name="Euro / US Dollar")
        self.assertEqual(quote.last, 1.10)
        self.assertEqual(quote.quote_type, "reference")
        self.assertEqual(quote.status, DataStatus.HISTORICAL)
        self.assertEqual(quote.timestamp.date().isoformat(), "2026-11-25")
        self.assertIsNone(quote.bid)
        self.assertIsNone(quote.ask)

    def test_inverse_pair_is_reciprocal(self):
        adapter = EcbForexAdapter()
        with patch.object(adapter, "_get", return_value=ECB_CSV):
            quote = adapter.fetch_quote(symbol="USDEUR", name="US Dollar / Euro")
        self.assertAlmostEqual(quote.last, 1 / 1.10, places=6)

    def test_cross_rate_uses_eur_pivot(self):
        adapter = EcbForexAdapter()
        usd = ECB_CSV
        jpy = ECB_CSV.replace("USD", "JPY").replace("1.05", "160.0").replace("1.10", "162.0")
        with patch.object(adapter, "_get", side_effect=lambda url, accept: (
            jpy if "JPY" in url else usd
        )):
            quote = adapter.fetch_quote(symbol="USDJPY", name="US Dollar / Japanese Yen")
        self.assertAlmostEqual(quote.last, 162.0 / 1.10, places=6)

    def test_malformed_pair_is_unavailable(self):
        adapter = EcbForexAdapter()
        quote = adapter.fetch_quote(symbol="GOLD", name="Gold")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIn("currency pair", quote.reason)

    def test_ecb_transport_failure_is_unavailable(self):
        adapter = EcbForexAdapter()
        with patch.object(adapter, "_get", side_effect=ProviderError("ECB timeout")):
            quote = adapter.fetch_quote(symbol="EURUSD", name="Euro / US Dollar")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIsNone(quote.last)

    def test_ecb_non_positive_rate_is_rejected(self):
        adapter = EcbForexAdapter()
        bad = ECB_CSV.replace("1.10", "0")
        with patch.object(adapter, "_get", return_value=bad):
            quote = adapter.fetch_quote(symbol="EURUSD", name="Euro / US Dollar")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)


class CoinGeckoAdapterTests(unittest.TestCase):
    def test_known_symbol_maps_to_coin_id(self):
        adapter = CoinGeckoCryptoAdapter()
        self.assertEqual(adapter.coin_id("BTCUSD"), "bitcoin")
        self.assertEqual(adapter.coin_id("btcusdt"), "bitcoin")
        self.assertIsNone(adapter.coin_id("DOGEUSD"))

    def test_successful_snapshot_uses_provider_timestamp(self):
        adapter = CoinGeckoCryptoAdapter()
        observed = int(datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc).timestamp())
        payload = {"bitcoin": {"usd": 95000.5, "last_updated_at": observed}}
        with patch.object(adapter, "_get_json", return_value=payload):
            quote = adapter.fetch_quote(symbol="BTCUSD", name="Bitcoin / US Dollar")
        self.assertEqual(quote.last, 95000.5)
        self.assertEqual(quote.quote_type, "mid")
        self.assertEqual(int(quote.timestamp.timestamp()), observed)
        self.assertEqual(quote.market_group, "crypto")

    def test_unmapped_symbol_is_unavailable(self):
        adapter = CoinGeckoCryptoAdapter()
        quote = adapter.fetch_quote(symbol="DOGEUSD", name="Dogecoin")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIn("asset id", quote.reason)

    def test_missing_price_is_unavailable(self):
        adapter = CoinGeckoCryptoAdapter()
        with patch.object(adapter, "_get_json", return_value={"bitcoin": {"usd": None}}):
            quote = adapter.fetch_quote(symbol="BTCUSD", name="Bitcoin / US Dollar")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)

    def test_rate_limit_is_reported_with_retry_after(self):
        """A 429 must be distinguishable from an outage in the UNAVAILABLE reason.

        Patch the raw transport, not the limiter: this test asserts the error
        message, while backoff/cooldown behaviour is tested separately in
        ``test_provider_policy`` with a fake clock.
        """
        adapter = CoinGeckoCryptoAdapter()
        from app.provider_policy import ProviderLimiter

        # Fake clock advances when "sleeping" so a cooldown deadline is reached
        # without any real wall-clock wait.
        now = [0.0]

        def advance(seconds: float) -> None:
            now[0] += max(seconds, 0.0)

        no_sleep_limiter = ProviderLimiter(clock=lambda: now[0], sleep=advance)
        with patch("app.provider_policy.LIMITER", no_sleep_limiter), \
             patch.object(adapter, "_raw_get", side_effect=ProviderError(
                "coingecko-public returned HTTP 429 (Retry-After: 60s)"
            )):
            quote = adapter.fetch_quote(symbol="BTCUSD", name="Bitcoin / US Dollar")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertIn("429", quote.reason)
        self.assertIn("Retry-After: 60", quote.reason)
        self.assertIsNone(quote.last)

    def test_future_provider_timestamp_is_clamped_to_retrieval(self):
        adapter = CoinGeckoCryptoAdapter()
        future = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
        with patch.object(adapter, "_get_json",
                           return_value={"bitcoin": {"usd": 100.0, "last_updated_at": future}}):
            quote = adapter.fetch_quote(symbol="BTCUSD", name="Bitcoin / US Dollar")
        self.assertLessEqual(quote.timestamp, quote.retrieved_at)


class ExchangeTimezoneTests(unittest.TestCase):
    def test_yahoo_timezone_is_carried_into_the_quote(self):
        adapter = UsEquitiesAdapter()
        with patch.object(adapter, "_get_json", return_value=_yahoo_payload([100.0, 103.0])):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        self.assertEqual(quote.exchange_timezone, "America/New_York")
        payload = quote.to_payload()
        local = payload["timestamp_exchange_local"]
        self.assertTrue("T" in local and ("-04:00" in local or "-05:00" in local))

    def test_india_timezone_is_asia_kolkata_and_offset_is_plus_0530(self):
        adapter = IndiaEquitiesAdapter()
        payload = _yahoo_payload([1400.0, 1450.5])
        payload["chart"]["result"][0]["meta"] = {"exchangeTimezoneName": "Asia/Kolkata"}
        with patch.object(adapter, "_get_json", return_value=payload):
            quote = adapter.fetch_quote(symbol="RELIANCE", name="Reliance Industries Ltd.")
        self.assertEqual(quote.exchange_timezone, "Asia/Kolkata")
        self.assertTrue(quote.to_payload()["timestamp_exchange_local"].endswith("+05:30"))

    def test_invalid_timezone_is_not_guessed(self):
        adapter = UsEquitiesAdapter()
        payload = _yahoo_payload([100.0, 103.0])
        payload["chart"]["result"][0]["meta"] = {"exchangeTimezoneName": "Not/AZone"}
        with patch.object(adapter, "_get_json", return_value=payload):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        self.assertIsNone(quote.exchange_timezone)
        self.assertIsNone(quote.to_payload()["timestamp_exchange_local"])

    def test_ecb_reference_fixing_claims_no_exchange_timezone(self):
        """A daily reference fixing has no session; no timezone is invented."""
        adapter = EcbForexAdapter()
        with patch.object(adapter, "_get", return_value=ECB_CSV):
            quote = adapter.fetch_quote(symbol="EURUSD", name="Euro / US Dollar")
        self.assertIsNone(quote.exchange_timezone)
        self.assertIsNone(quote.to_payload()["timestamp_exchange_local"])

    def test_quote_rejects_unknown_iana_timezone(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            MarketQuote(
                symbol="AAPL", name="Apple Inc.", asset_class="equity",
                market_group="us", exchange="NASDAQ", currency="USD",
                last=100.0, timestamp=datetime(2026, 11, 26, tzinfo=timezone.utc),
                retrieved_at=datetime(2026, 11, 26, tzinfo=timezone.utc),
                status=DataStatus.HISTORICAL, source="manual-review",
                exchange_timezone="Mars/Olympus",
            )


class QuoteRoutingTests(unittest.TestCase):
    def test_unknown_market_group_is_contained_as_unavailable(self):
        quotes = quotes_for_instruments([{
            "symbol": "MYSTERY", "name": "Mystery", "market": "equities",
            "market_group": "atlantis", "venue": "X", "currency": "USD",
        }])
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].status, DataStatus.UNAVAILABLE)
        self.assertIn("no adapter", quotes[0].reason)

    def test_adapter_exception_does_not_break_the_batch(self):
        us = ADAPTERS["us"]
        crypto = ADAPTERS["crypto"]
        with patch.object(us, "fetch_quote", side_effect=RuntimeError("boom")), \
             patch.object(crypto, "fetch_quote", side_effect=ProviderError("down")):
            quotes = quotes_for_instruments([
                {"symbol": "AAPL", "name": "Apple Inc.", "market": "equities",
                 "market_group": "us", "venue": "NASDAQ", "currency": "USD"},
                {"symbol": "BTCUSD", "name": "Bitcoin", "market": "digital_assets",
                 "market_group": "crypto", "venue": "Multi-venue", "currency": "USD"},
            ])
        self.assertEqual(len(quotes), 2)
        self.assertTrue(all(q.status is DataStatus.UNAVAILABLE for q in quotes))
        self.assertIsNone(quotes[0].last)
        self.assertIsNone(quotes[1].last)

    def test_quotes_are_json_serializable_without_attested_sources(self):
        adapter = UsEquitiesAdapter()
        with patch.object(adapter, "_get_json", return_value=_yahoo_payload([100.0, 101.0])):
            quote = adapter.fetch_quote(symbol="AAPL", name="Apple Inc.")
        payload = quote.to_payload()
        self.assertNotIn("attested_sources", payload)
        encoded = json.dumps(payload)
        self.assertIn("yahoo-us-equities", encoded)


if __name__ == "__main__":
    unittest.main()
