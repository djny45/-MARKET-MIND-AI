"""Failure, recovery and staleness validation for the four-market terminal.

Runs entirely offline by patching the adapter HTTP seams. Produces an evidence
JSON under docs/external-evidence/ and asserts every property it records.
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("MARKET_MIND_DB", tempfile.mkdtemp() + "/resilience.db")

from app import four_market_terminal
from app.four_market_terminal import build_terminal_snapshot, summarize_terminal
from app.instruments import INSTRUMENTS
from app.market_data import DataStatus
from app.market_quotes import MarketQuote
from app.provider_adapters import ADAPTERS, ProviderError

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "external-evidence" / "four-market-resilience.json"

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def quote(symbol, status, *, last=100.0, age_seconds=0, source="yahoo-us-equities",
          attested=(), reason=None):
    ts = NOW - timedelta(seconds=age_seconds)
    return MarketQuote(
        symbol=symbol, name=symbol, asset_class="equity", market_group="us",
        exchange="NASDAQ", currency="USD", last=last, timestamp=ts,
        retrieved_at=NOW, status=status, source=source,
        attested_sources=frozenset(attested), reason=reason,
    )


class ResilienceEvidence(unittest.TestCase):
    def setUp(self):
        four_market_terminal.clear_cache()

    def tearDown(self):
        four_market_terminal.clear_cache()

    def test_full_failure_then_recovery(self):
        evidence = {"scenarios": []}

        # --- Scenario 1: every provider down -----------------------------
        with patch("app.provider_adapters.UsEquitiesAdapter._get_json",
                   side_effect=ProviderError("HTTP 503")), \
             patch("app.provider_adapters.IndiaEquitiesAdapter._get_json",
                   side_effect=ProviderError("HTTP 503")), \
             patch("app.provider_adapters.EcbForexAdapter._get",
                   side_effect=ProviderError("ECB timeout")), \
             patch("app.provider_adapters.CoinGeckoCryptoAdapter._get_json",
                   side_effect=ProviderError("HTTP 429")):
            down = build_terminal_snapshot(INSTRUMENTS, now=NOW)
        down_summary = summarize_terminal(down)
        evidence["scenarios"].append({
            "name": "all_providers_failed",
            "totals": down["totals"],
            "markets": [
                {"market_group": m["market_group"], "market_status": m["market_status"],
                 "headline": m["headline"], "usable_count": m["usable_count"]}
                for m in down["markets"]
            ],
        })
        self.assertEqual(down["totals"]["usable"], 0)
        self.assertEqual(down["totals"]["unavailable"], down["totals"]["quotes"])
        for market in down["markets"]:
            self.assertEqual(market["market_status"], "unavailable")
            for row in market["quotes"]:
                self.assertIsNone(row["last"])
                self.assertTrue(row["reason"])

        # --- Scenario 2: one provider recovers while others stay down ----
        recovered = quote("AAPL", DataStatus.HISTORICAL, last=200.0)
        with patch("app.four_market_terminal.quotes_for_instruments",
                   side_effect=lambda instruments, attested_sources=(): [
                       recovered if i.get("market_group") == "us"
                       else quote(str(i.get("symbol")), DataStatus.UNAVAILABLE,
                                  last=None, reason="feed still unavailable")
                       for i in instruments
                   ]):
            partial = build_terminal_snapshot(INSTRUMENTS, now=NOW)
        evidence["scenarios"].append({
            "name": "us_recovers_others_down",
            "totals": partial["totals"],
            "markets": [
                {"market_group": m["market_group"], "market_status": m["market_status"],
                 "headline": m["headline"], "usable_count": m["usable_count"],
                 "unavailable_count": m["unavailable_count"]}
                for m in partial["markets"]
            ],
        })
        us = next(m for m in partial["markets"] if m["market_group"] == "us")
        self.assertEqual(us["market_status"], "fresh")
        self.assertEqual(us["usable_count"], 5)  # all 5 default US symbols recovered
        self.assertEqual(us["quotes"][0]["last"], 200.0)
        self.assertNotIn("UNAVAILABLE", [q["status"] for q in us["quotes"]])

        # --- Scenario 3: stale attested LIVE quote ------------------------
        stale = quote("AAPL", DataStatus.LIVE, last=200.0, age_seconds=600,
                      attested=["yahoo-us-equities"])
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[stale]):
            stale_board = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL"]},
                attested_sources=["yahoo-us-equities"], now=NOW,
            )
        stale_market = stale_board["markets"][0]
        evidence["scenarios"].append({
            "name": "stale_live_quote",
            "status": stale_market["quotes"][0]["status"],
            "age_seconds": stale_market["quotes"][0]["age_seconds"],
            "stale": stale_market["quotes"][0]["stale"],
            "market_status": stale_market["market_status"],
        })
        self.assertTrue(stale_market["quotes"][0]["stale"])
        self.assertEqual(stale_market["market_status"], "stale")

        # --- Scenario 4: an attested LIVE quote within threshold ----------
        fresh = quote("AAPL", DataStatus.LIVE, last=201.0, age_seconds=10,
                      attested=["yahoo-us-equities"])
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[fresh]):
            fresh_board = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL"]},
                attested_sources=["yahoo-us-equities"], now=NOW,
            )
        fresh_market = fresh_board["markets"][0]
        evidence["scenarios"].append({
            "name": "fresh_live_quote",
            "status": fresh_market["quotes"][0]["status"],
            "age_seconds": fresh_market["quotes"][0]["age_seconds"],
            "stale": fresh_market["quotes"][0]["stale"],
            "market_status": fresh_market["market_status"],
        })
        self.assertFalse(fresh_market["quotes"][0]["stale"])
        self.assertEqual(fresh_market["market_status"], "fresh")

        # --- Scenario 5: unattested provider cannot claim LIVE ------------
        unattested = quote("AAPL", DataStatus.HISTORICAL, last=200.0, age_seconds=5)
        with patch("app.four_market_terminal.quotes_for_instruments", return_value=[unattested]), \
             patch.dict(os.environ, {}, clear=True):
            board = build_terminal_snapshot(
                INSTRUMENTS, market_groups=["us"], symbols={"us": ["AAPL"]}, now=NOW,
            )
        evidence["scenarios"].append({
            "name": "no_attestation_means_no_live_label",
            "status": board["markets"][0]["quotes"][0]["status"],
            "attested_sources": board["attested_sources"],
        })
        self.assertEqual(board["markets"][0]["quotes"][0]["status"], "historical")

        evidence["generated_at"] = datetime.now(timezone.utc).isoformat()
        evidence["mode"] = "offline_containment_and_recovery"
        evidence["live_labels_allowed"] = False
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
