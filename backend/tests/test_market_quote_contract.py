"""Contract tests for the unified four-market normalized quote model."""
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.market_data import DataStatus, status_allowed_for_source
from app.market_quotes import MarketQuote


def _ts() -> datetime:
    return datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


class MarketQuoteContractTests(unittest.TestCase):
    def test_unavailable_is_a_first_class_status(self):
        self.assertEqual(DataStatus.UNAVAILABLE.value, "unavailable")
        self.assertTrue(status_allowed_for_source(DataStatus.UNAVAILABLE, "coingecko-public"))
        # An UNAVAILABLE quote must not be accepted as a LIVE claim.
        self.assertNotEqual(DataStatus.UNAVAILABLE, DataStatus.LIVE)

    def test_quote_requires_attribution_and_status(self):
        quote = MarketQuote(
            symbol="NIFTY50", name="NIFTY 50", asset_class="index",
            exchange="NSE", currency="INR", last=24600.5,
            timestamp=_ts(), retrieved_at=_ts(),
            status=DataStatus.UNAVAILABLE, source="nse-public",
            reason="licensing review pending",
        )
        self.assertEqual(quote.asset_class, "index")
        self.assertEqual(quote.status, DataStatus.UNAVAILABLE)
        self.assertEqual(quote.reason, "licensing review pending")

    def test_live_requires_attested_source(self):
        with self.assertRaises(ValidationError):
            MarketQuote(
                symbol="BTCUSD", name="Bitcoin", asset_class="crypto",
                exchange="BINANCE", currency="USD", last=100.0,
                timestamp=_ts(), retrieved_at=_ts(),
                status=DataStatus.LIVE, source="unattested-source",
            )

    def test_quote_has_no_executable_bid_ask_by_default(self):
        quote = MarketQuote(
            symbol="EURUSD", name="Euro / US Dollar", asset_class="forex",
            exchange="reference", currency="USD", last=1.08,
            timestamp=_ts(), retrieved_at=_ts(),
            status=DataStatus.DELAYED, source="ecb-reference",
            attested_sources=frozenset({"ecb-reference"}),
        )
        self.assertIsNone(quote.bid)
        self.assertIsNone(quote.ask)
        self.assertEqual(quote.quote_type, "indicative")

    def test_synthetic_quote_is_forbidden_from_claiming_live(self):
        with self.assertRaises(ValidationError):
            MarketQuote(
                symbol="BTCUSD", name="Bitcoin", asset_class="crypto",
                exchange="fixture", currency="USD", last=100.0,
                timestamp=_ts(), retrieved_at=_ts(),
                status=DataStatus.SYNTHETIC, source="binance-public",
            )


if __name__ == "__main__":
    unittest.main()
