"""Tests for four-market OHLCV ingestion: provenance, intervals and failures."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import four_market_bars as bars
from app.four_market_bars import IngestionError, ingest_bars, interval_support
from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.provider_adapters import ProviderError

NOW = datetime.now(timezone.utc)


def yahoo_payload(closes, stamps=None):
    stamps = stamps or [
        int((NOW - timedelta(days=len(closes)-i)).timestamp()) for i in range(len(closes))
    ]
    return {
        "chart": {
            "error": None,
            "result": [{
                "timestamp": stamps,
                "meta": {
                    "exchangeTimezoneName": "Asia/Kolkata",
                    "currency": "INR",
                },
                "indicators": {"quote": [{
                    "open": closes, "high": [c + 2 for c in closes],
                    "low": [c - 2 for c in closes], "close": closes,
                    "volume": [1000] * len(closes),
                }]},
            }],
        },
    }


class IntervalSupportTests(unittest.TestCase):
    def test_all_four_markets_are_declared(self):
        for group in ("us", "india", "forex", "crypto"):
            row = interval_support(group)
            self.assertIn("supported_intervals", row)
            self.assertTrue(row["supported_intervals"])

    def test_forex_only_supports_daily(self):
        self.assertEqual(interval_support("forex")["supported_intervals"], ["1d"])

    def test_equities_and_crypto_support_four_intervals(self):
        for group in ("us", "india", "crypto"):
            self.assertEqual(
                interval_support(group)["supported_intervals"],
                ["15m", "1h", "4h", "1d"],
            )

    def test_exchange_timezones_declared_only_where_real(self):
        self.assertEqual(interval_support("us")["exchange_timezone"], "America/New_York")
        self.assertEqual(interval_support("india")["exchange_timezone"], "Asia/Kolkata")
        self.assertIsNone(interval_support("forex")["exchange_timezone"])
        self.assertIsNone(interval_support("crypto")["exchange_timezone"])

    def test_unknown_market_group(self):
        with self.assertRaises(ValueError):
            interval_support("mars")


class ValidationTests(unittest.TestCase):
    def test_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):
            ingest_bars("AAPL", "us", "2m")

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            ingest_bars("AAPL", "us", "1d", limit=0)

    def test_invalid_symbol_rejected(self):
        with self.assertRaises(ValueError):
            ingest_bars("", "us")

    def test_invalid_bar_is_dropped_not_repaired(self):
        good = bars._valid_bar(NOW, 100, 102, 99, 101, 1000)
        self.assertIsNotNone(good)
        crossed = bars._valid_bar(NOW, 100, 98, 99, 101, 1000)
        self.assertIsNone(crossed)
        negative = bars._valid_bar(NOW, -1, 2, -2, 1, 1000)
        self.assertIsNone(negative)
        nan = bars._valid_bar(NOW, float("nan"), 2, 1, 1, 1000)
        self.assertIsNone(nan)

    def test_provider_symbol_mapping(self):
        self.assertEqual(bars._provider_symbol("RELIANCE", "india", "NSE"), "RELIANCE.NS")
        self.assertEqual(bars._provider_symbol("RELIANCE", "india", "BSE"), "RELIANCE.BO")
        self.assertEqual(bars._provider_symbol("NIFTY50", "india"), "^NSEI")
        self.assertEqual(bars._provider_symbol("SPX", "us"), "^GSPC")


class IngestionTests(unittest.TestCase):
    def setUp(self):
        # Use a fake-clock limiter with no real waits: otherwise a simulated
        # 429 would exercise real 60s backoff. Production pacing is tested in
        # test_provider_policy with its own explicit fake-clock assertions.
        from app.provider_policy import ProviderLimiter

        self.now = [0.0]

        def advance(seconds):
            self.now[0] += max(seconds, 0.0)

        self.test_limiter = ProviderLimiter(clock=lambda: self.now[0], sleep=advance)
        self.limiter_patch = patch("app.provider_policy.LIMITER", self.test_limiter)
        self.limiter_patch.start()

    def tearDown(self):
        self.limiter_patch.stop()
    def test_us_daily_ingestion_carries_provenance(self):
        batch = MarketDataBatch(
            symbol="AAPL", interval="1d", status=DataStatus.HISTORICAL,
            source="legacy", retrieved_at=NOW,
            bars=[OHLCVBar(timestamp=NOW - timedelta(days=1),
                           open=100, high=102, low=99, close=101, volume=1000)],
        )
        with patch("app.yahoo_finance_adapter.YahooFinanceAdapter.get_bars_sync",
                   return_value=batch), \
             patch("app.four_market_bars.market_store.store_batch", return_value={"inserted": 1}):
            result = ingest_bars("AAPL", "us", "1d", store=True)
        self.assertEqual(result["source"], "yahoo-us-equities")
        self.assertEqual(result["status_label"], "HISTORICAL")
        self.assertEqual(result["exchange_timezone"], "America/New_York")
        self.assertEqual(result["observation_count"], 1)
        self.assertEqual(result["storage"], {"inserted": 1})
        self.assertFalse(result["execution"]["real_money"])

    def test_india_bse_symbol_is_mapped_in_warnings(self):
        batch = MarketDataBatch(
            symbol="TCS", interval="1d", status=DataStatus.HISTORICAL,
            source="legacy", retrieved_at=NOW,
            bars=[OHLCVBar(timestamp=NOW - timedelta(days=1),
                           open=100, high=102, low=99, close=101, volume=1000)],
        )
        with patch("app.yahoo_finance_adapter.YahooFinanceAdapter.get_bars_sync",
                   return_value=batch), \
             patch("app.four_market_bars.market_store.store_batch", return_value={}):
            result = ingest_bars("TCS", "india", "1d", venue="BSE", store=False)
        self.assertTrue(any("TCS.BO" in warning for warning in result["warnings"]))
        self.assertTrue(any("Asia/Kolkata" in warning for warning in result["warnings"]))
        self.assertIsNone(result["storage"])

    def test_forex_single_fixing_becomes_honest_bar(self):
        csv_body = (
            "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
            "EXR,D,USD,EUR,SP00,A,2026-11-24,1.05\n"
            "EXR,D,USD,EUR,SP00,A,2026-11-25,1.10\n"
        )
        with patch("app.four_market_bars._ecb_get", return_value=csv_body), \
             patch("app.four_market_bars.market_store.store_batch", return_value={}):
            result = ingest_bars("EURUSD", "forex", "1d", store=False)
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["source"], "ecb-reference-rates")
        bar = result["bars"][0]
        self.assertEqual(bar["open"], bar["high"])
        self.assertEqual(bar["high"], bar["low"])
        self.assertEqual(bar["low"], bar["close"])
        self.assertTrue(any("single published fixing" in w for w in result["warnings"]))

    def test_forex_rejects_intraday_interval(self):
        with self.assertRaises(IngestionError):
            ingest_bars("EURUSD", "forex", "1h")

    def test_crypto_ohlc_without_volume_is_handled(self):
        payload = [
            [int((NOW - timedelta(hours=i)).timestamp() * 1000),
             100.0 + i, 102.0 + i, 99.0 + i, 101.0 + i]
            for i in range(5, 0, -1)
        ]
        with patch("app.four_market_bars._get_json", return_value=payload), \
             patch("app.four_market_bars.market_store.store_batch", return_value={}):
            result = ingest_bars("BTCUSD", "crypto", "1d", store=False)
        self.assertEqual(result["observation_count"], 5)
        self.assertEqual(result["source"], "coingecko-public")
        self.assertTrue(all(bar["volume"] == 0 for bar in result["bars"]))
        self.assertTrue(any("not provided" in w for w in result["warnings"]))

    def test_crypto_unmapped_symbol_is_rejected(self):
        with self.assertRaises(IngestionError):
            ingest_bars("DOGEUSD", "crypto", "1d")

    def test_missing_candles_produce_no_bars(self):
        with patch("app.four_market_bars._get_json", return_value=[]):
            with self.assertRaises(IngestionError):
                ingest_bars("BTCUSD", "crypto", "1d", store=False)

    def test_invalid_provider_response_is_rejected(self):
        with patch("app.four_market_bars._get_json", return_value={"error": "bad"}):
            with self.assertRaises(IngestionError):
                ingest_bars("BTCUSD", "crypto", "1d", store=False)

    def test_provider_failure_is_surfaced_not_filled(self):
        with patch("app.four_market_bars._get_json",
                   side_effect=ProviderError("coingecko-public returned HTTP 429 (Retry-After: 60s)")):
            with self.assertRaises(ProviderError):
                ingest_bars("BTCUSD", "crypto", "1d", store=False)

    def test_stale_candles_keep_their_own_timestamp(self):
        """Old bars are stored under their real event time, not refreshed."""
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        batch = MarketDataBatch(
            symbol="AAPL", interval="1d", status=DataStatus.HISTORICAL,
            source="legacy", retrieved_at=NOW,
            bars=[OHLCVBar(timestamp=old, open=1, high=2, low=0.5, close=1.5, volume=10)],
        )
        with patch("app.yahoo_finance_adapter.YahooFinanceAdapter.get_bars_sync", return_value=batch), \
             patch("app.four_market_bars.market_store.store_batch", return_value={}):
            result = ingest_bars("AAPL", "us", "1d", store=False)
        self.assertTrue(result["first_timestamp"].startswith("2020-01-01"))
        # retrieved_at is fresh, so staleness is visible rather than hidden.
        self.assertGreater(result["retrieved_at"][:4], "2020")


if __name__ == "__main__":
    unittest.main()
