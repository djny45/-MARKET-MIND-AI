import unittest

from app.autohedge_market_making_research import (
    BookSnapshot,
    MarketMakingResearchConfig,
    calculate_research_quotes,
    simulate_fill,
)


class AutoHedgeMarketMakingResearchTests(unittest.TestCase):
    def setUp(self):
        self.book = BookSnapshot(
            bid=99.0, ask=101.0, timestamp=1000.0,
            bid_size=5.0, ask_size=4.0,
        )

    def test_quote_calculation_is_indicative_only(self):
        result = calculate_research_quotes(
            self.book, MarketMakingResearchConfig(), now=1001.0
        )
        self.assertEqual(result["mode"], "research_only_indicative_quotes")
        self.assertFalse(result["broker_execution"])
        self.assertFalse(result["orders_submitted"])
        self.assertAlmostEqual(result["mid_price"], 100.0)

    def test_rejects_stale_book(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            calculate_research_quotes(
                self.book,
                MarketMakingResearchConfig(max_data_age_seconds=10),
                now=1011.0,
            )

    def test_rejects_inverted_book(self):
        bad = BookSnapshot(bid=102, ask=101, timestamp=1000)
        with self.assertRaisesRegex(ValueError, "crossed"):
            calculate_research_quotes(
                bad, MarketMakingResearchConfig(), now=1001
            )

    def test_buy_fill_is_pure_simulation(self):
        result = simulate_fill("buy", 100, 2, 1000, 0, fee_bps=10)
        self.assertEqual(result["status"], "simulated_fill")
        self.assertAlmostEqual(result["quote_balance_after"], 799.8)
        self.assertEqual(result["base_balance_after"], 2)
        self.assertFalse(result["broker_execution"])

    def test_sell_fill_checks_inventory(self):
        result = simulate_fill("sell", 100, 2, 0, 1)
        self.assertEqual(result["status"], "rejected_insufficient_base")
        self.assertFalse(result["broker_execution"])

    def test_bad_inputs_fail_closed(self):
        for side in ("market", "", None):
            with self.subTest(side=side):
                with self.assertRaises(ValueError):
                    simulate_fill(side, 100, 1, 1000, 1)


if __name__ == "__main__":
    unittest.main()
