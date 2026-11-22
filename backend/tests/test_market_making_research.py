import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.market_making_research import calculate_market_making_research


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class MarketMakingResearchTests(unittest.TestCase):
    def snapshot(self, bid="99", ask="101", timestamp=None):
        return {"best_bid": bid, "best_ask": ask,
                "timestamp": (timestamp or NOW).isoformat()}

    def test_calculates_mid_spread_and_inventory_skew(self):
        result = calculate_market_making_research(
            self.snapshot(), observed_at=NOW, half_spread_bps=10,
            inventory=2, inventory_skew_bps=5,
        )
        self.assertEqual(Decimal(result["mid"]), Decimal("100"))
        self.assertEqual(Decimal(result["spread"]), Decimal("2"))
        self.assertLess(Decimal(result["indicative_bid"]), Decimal("99"))
        self.assertLess(Decimal(result["indicative_ask"]), Decimal("101"))
        self.assertEqual(result["mode"], "research_only_indicative")

    def test_rejects_crossed_book(self):
        with self.assertRaisesRegex(ValueError, "crossed"):
            calculate_market_making_research(self.snapshot("101", "100"), observed_at=NOW)

    def test_rejects_stale_and_future_books(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            calculate_market_making_research(
                self.snapshot(timestamp=NOW - timedelta(seconds=31)), observed_at=NOW
            )
        with self.assertRaisesRegex(ValueError, "future"):
            calculate_market_making_research(
                self.snapshot(timestamp=NOW + timedelta(seconds=1)), observed_at=NOW
            )

    def test_rejects_non_finite_and_non_positive_prices(self):
        for bid in ("NaN", "Infinity", "0", "-2"):
            with self.subTest(bid=bid):
                with self.assertRaises(ValueError):
                    calculate_market_making_research(self.snapshot(bid=bid), observed_at=NOW)

    def test_rejects_naive_timestamp(self):
        snap = self.snapshot(timestamp=datetime(2026, 1, 1))
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            calculate_market_making_research(snap, observed_at=NOW)


if __name__ == "__main__":
    unittest.main()
