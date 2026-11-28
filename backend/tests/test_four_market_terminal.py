"""Tests for the four-market terminal assembly service.

These assert the properties an operator actually relies on: per-market
attribution, per-quote staleness, honest UNAVAILABLE handling, and the fact
that a live/delayed label is impossible without operator attestation.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.four_market_terminal import (
    DEFAULT_WATCH,
    DISPLAY_ORDER,
    build_terminal_snapshot,
    cached_terminal_snapshot,
    clear_cache,
    summarize_terminal,
)
from app.instruments import INSTRUMENTS
from app.market_data import DataStatus
from app.market_quotes import MarketQuote
from app.provider_adapters import ProviderError, UsEquitiesAdapter

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def _quote(symbol, *, status=DataStatus.HISTORICAL, last=100.0,
           timestamp=None, source="yahoo-us-equities", group="us",
           attested=frozenset(), reason=None):
    ts = timestamp or NOW - timedelta(minutes=5)
    return MarketQuote(
        symbol=symbol, name=f"{symbol} instrument", asset_class="equity",
        market_group=group, exchange="NASDAQ", currency="USD",
        last=last, timestamp=ts, retrieved_at=NOW, status=status,
        source=source, attested_sources=attested,
        reason=reason or ("feed disabled for this instrument"
                          if status is DataStatus.UNAVAILABLE else None),
    )


def _offline_adapters():
    """Patch every adapter seam to fail, so no test touches the network."""
    patcher = patch.object(
        UsEquitiesAdapter, "_get_json", side_effect=ProviderError("offline")
    )
    return patcher


class TerminalAssemblyTests(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def tearDown(self):
        clear_cache()

    def test_board_covers_all_four_markets_in_display_order(self):
        with _offline_adapters(), patch(
            "app.provider_adapters.EcbForexAdapter._get", side_effect=ProviderError("offline")
        ):
            snapshot = build_terminal_snapshot(INSTRUMENTS, now=NOW)
        self.assertEqual([m["market_group"] for m in snapshot["markets"]], list(DISPLAY_ORDER))
        self.assertEqual(snapshot["totals"]["markets"], 4)

    def test_offline_board_reports_unavailable_without_inventing_prices(self):
        with _offline_adapters(), patch(
            "app.provider_adapters.EcbForexAdapter._get", side_effect=ProviderError("offline")
        ), patch("app.provider_adapters.CoinGeckoCryptoAdapter._get_json",
                 side_effect=ProviderError("offline")), patch(
            "app.provider_adapters.IndiaEquitiesAdapter._get_json",
            side_effect=ProviderError("offline")):
            snapshot = build_terminal_snapshot(INSTRUMENTS, now=NOW)
        for market in snapshot["markets"]:
            self.assertEqual(market["market_status"], "unavailable")
            self.assertEqual(market["usable_count"], 0)
            for quote in market["quotes"]:
                self.assertEqual(quote["status"], "unavailable")
                self.assertIsNone(quote["last"])
                self.assertTrue(quote["reason"])
                self.assertEqual(quote["status_label"], "UNAVAILABLE")
        self.assertEqual(snapshot["totals"]["usable"], 0)

    def test_each_quote_carries_source_and_both_timestamps(self):
        with _offline_adapters(), patch(
            "app.provider_adapters.EcbForexAdapter._get", side_effect=ProviderError("offline")
        ), patch("app.provider_adapters.CoinGeckoCryptoAdapter._get_json",
                 side_effect=ProviderError("offline")), patch(
            "app.provider_adapters.IndiaEquitiesAdapter._get_json",
            side_effect=ProviderError("offline")):
            snapshot = build_terminal_snapshot(INSTRUMENTS, now=NOW)
        for market in snapshot["markets"]:
            for quote in market["quotes"]:
                self.assertTrue(quote["source"])
                self.assertIn("timestamp", quote)
                self.assertIn("retrieved_at", quote)
                self.assertIn("age_seconds", quote)
                self.assertIn("max_age_seconds", quote)

    def test_stale_live_quote_is_flagged(self):
        old = NOW - timedelta(minutes=10)  # live threshold is 60s
        quote = _quote("AAPL", status=DataStatus.LIVE, timestamp=old,
                       attested=frozenset({"yahoo-us-equities"}))
        with patch("app.four_market_terminal.quotes_for_instruments",
                   return_value=[quote]):
            snapshot = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL"]},
                attested_sources=["yahoo-us-equities"], now=NOW,
            )
        market = snapshot["markets"][0]
        self.assertEqual(market["stale_count"], 1)
        self.assertEqual(market["market_status"], "stale")
        self.assertTrue(market["quotes"][0]["stale"])

    def test_fresh_live_quote_is_not_stale(self):
        quote = _quote("AAPL", status=DataStatus.LIVE,
                       timestamp=NOW - timedelta(seconds=10),
                       attested=frozenset({"yahoo-us-equities"}))
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[quote]):
            snapshot = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL"]},
                attested_sources=["yahoo-us-equities"], now=NOW,
            )
        market = snapshot["markets"][0]
        self.assertEqual(market["market_status"], "fresh")
        self.assertEqual(market["stale_count"], 0)
        self.assertFalse(market["quotes"][0]["stale"])

    def test_partial_staleness_is_reported_separately(self):
        fresh = _quote("AAPL", status=DataStatus.LIVE, timestamp=NOW - timedelta(seconds=5),
                       attested=frozenset({"yahoo-us-equities"}))
        stale = _quote("MSFT", status=DataStatus.LIVE, timestamp=NOW - timedelta(minutes=30),
                       attested=frozenset({"yahoo-us-equities"}))
        with patch("app.four_market_terminal.quotes_for_instruments",
                   return_value=[fresh, stale]):
            snapshot = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL", "MSFT"]},
                attested_sources=["yahoo-us-equities"], now=NOW,
            )
        market = snapshot["markets"][0]
        self.assertEqual(market["market_status"], "partially_stale")
        self.assertEqual(market["stale_count"], 1)
        self.assertEqual(market["usable_count"], 2)

    def test_unavailable_is_never_labelled_stale(self):
        quote = _quote("AAPL", status=DataStatus.UNAVAILABLE, last=None,
                       timestamp=NOW - timedelta(days=400))
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[quote]):
            snapshot = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL"]}, now=NOW,
            )
        row = snapshot["markets"][0]["quotes"][0]
        self.assertEqual(row["status"], "unavailable")
        self.assertFalse(row["stale"])
        self.assertIsNone(row["max_age_seconds"])

    def test_market_absent_from_catalogue_is_not_inferred(self):
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]):
            snapshot = build_terminal_snapshot(
                [], market_groups=["india"], now=NOW,
            )
        market = snapshot["markets"][0]
        self.assertEqual(market["headline"], "NOT IN CATALOGUE")
        self.assertEqual(market["quotes"], [])
        self.assertEqual(market["requested"], 0)

    def test_invalid_market_group_is_rejected(self):
        with self.assertRaises(ValueError):
            build_terminal_snapshot(INSTRUMENTS, market_groups=["mars"], now=NOW)

    def test_execution_boundary_is_reported(self):
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]):
            snapshot = build_terminal_snapshot(INSTRUMENTS, market_groups=["us"], now=NOW)
        self.assertFalse(snapshot["execution"]["broker_execution"])
        self.assertFalse(snapshot["execution"]["real_money"])
        self.assertEqual(snapshot["mode"], "four_market_research_terminal")

    def test_legend_documents_every_status(self):
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]):
            snapshot = build_terminal_snapshot(INSTRUMENTS, market_groups=["us"], now=NOW)
        statuses = {item["status"] for item in snapshot["legend"]["labels"]}
        self.assertEqual(
            statuses, {"live", "delayed", "historical", "synthetic", "unavailable"}
        )

    def test_default_watch_lists_only_catalogue_symbols(self):
        catalogue_symbols = {
            (item["market_group"], item["symbol"]) for item in INSTRUMENTS
        }
        for group, symbols in DEFAULT_WATCH.items():
            for symbol in symbols:
                with self.subTest(group=group, symbol=symbol):
                    self.assertIn((group, symbol), catalogue_symbols)


class TerminalSummaryTests(unittest.TestCase):
    def test_summary_reports_one_row_per_market(self):
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]):
            snapshot = build_terminal_snapshot(INSTRUMENTS, now=NOW)
        summary = summarize_terminal(snapshot)
        self.assertEqual(len(summary["markets"]), 4)
        for row in summary["markets"]:
            self.assertIn("market_status", row)
            self.assertIn("adapter", row)
            self.assertIn("requires_attestation", row)
        self.assertFalse(summary["execution"]["broker_execution"])


class TerminalCacheTests(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def tearDown(self):
        clear_cache()

    def test_second_call_hits_the_cache(self):
        clock = iter([1000.0, 1005.0, 1005.0])
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]) as spy:
            first = cached_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], ttl_seconds=15.0,
                clock=lambda: next(clock),
            )
            second = cached_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], ttl_seconds=15.0,
                clock=lambda: next(clock),
            )
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual(spy.call_count, 1)

    def test_ttl_zero_always_refetches(self):
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]) as spy:
            cached_terminal_snapshot(INSTRUMENTS, market_groups=["us"], ttl_seconds=0)
            cached_terminal_snapshot(INSTRUMENTS, market_groups=["us"], ttl_seconds=0)
        self.assertEqual(spy.call_count, 2)

    def test_attestation_change_bypasses_the_cache(self):
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[]) as spy:
            cached_terminal_snapshot(INSTRUMENTS, market_groups=["us"],
                                     attested_sources=[], ttl_seconds=15.0)
            cached_terminal_snapshot(INSTRUMENTS, market_groups=["us"],
                                     attested_sources=["yahoo-us-equities"], ttl_seconds=15.0)
        self.assertEqual(spy.call_count, 2)


if __name__ == "__main__":
    unittest.main()
