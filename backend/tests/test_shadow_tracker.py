import tempfile
import unittest
from pathlib import Path

from app.research_shadow_session import ShadowSessionEngine, make_backtest_config
from app.shadow_tracker import (
    DEMOTION_THRESHOLD_CYCLES,
    ShadowTracker,
    read_tracker_audit,
)


def _order(symbol, pnl, date, quantity=1.0, price=100.0):
    return {
        "symbol": symbol,
        "side": "BUY" if pnl >= 0 else "SELL",
        "quantity": quantity,
        "reference_price": price,
        "expected_pnl": pnl,
        "timestamp": f"2026-11-{date:02d}T09:00:00",
    }


class ShadowTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = Path(self.tmp.name) / "tracker.jsonl"
        self.engine = ShadowSessionEngine(make_backtest_config())
        self.tracker = ShadowTracker(self.engine, audit_path=self.audit)

    def tearDown(self):
        self.tmp.cleanup()

    def test_daily_report_aggregates_by_date_and_symbol(self):
        self.tracker.record_shadow_order("BTC", _order("BTC", 5.0, 5), run_id="r1")
        self.tracker.record_shadow_order("BTC", _order("BTC", -1.0, 5), run_id="r1")
        self.tracker.record_shadow_order("ETH", _order("ETH", 2.0, 5), run_id="r1")
        rows = self.tracker.daily_report("r1")
        self.assertEqual({(row.date, row.symbol) for row in rows}, {("2026-11-05", "BTC"), ("2026-11-05", "ETH")})
        btc = next(row for row in rows if row.symbol == "BTC")
        self.assertEqual(btc.total_pnl, 4.0)
        self.assertEqual(btc.order_count, 2)

    def test_demotion_after_ten_failing_cycles(self):
        for day in range(1, DEMOTION_THRESHOLD_CYCLES + 1):
            self.tracker.record_shadow_order("BTC", _order("BTC", -0.5, day), run_id="r1")
        evaluations = self.tracker.evaluate_strategies()
        self.assertEqual(evaluations["BTC"].consecutive_failing_cycles, DEMOTION_THRESHOLD_CYCLES)
        proposals = self.tracker.generate_demotion_proposals()
        self.assertEqual(len(proposals), 1)
        self.assertTrue(proposals[0].human_required)
        self.assertEqual(proposals[0].consecutive_failing_cycles, DEMOTION_THRESHOLD_CYCLES)
        result = self.tracker.demote("BTC", "reviewer-1", "system proposal")
        self.assertEqual(result["status"], "demoted")
        self.assertIn("BTC", self.tracker.demoted_symbols())

    def test_recovery_after_ten_clean_cycles(self):
        for day in range(1, 11):
            self.tracker.record_shadow_order("BTC", _order("BTC", -0.5, day), run_id="r1")
        self.tracker.generate_demotion_proposals()
        self.tracker.demote("BTC", "reviewer-1", "system proposal")
        for day in range(11, 21):
            self.tracker.record_shadow_order("BTC", _order("BTC", 1.0, day), run_id="r1")
        evaluations = self.tracker.evaluate_strategies()
        self.assertEqual(evaluations["BTC"].status, "recovered")
        self.assertNotIn("BTC", self.tracker.demoted_symbols())
        result = self.tracker.recover("BTC", "reviewer-1", "manual recovery")
        self.assertEqual(result["status"], "recovered")

    def test_report_and_audit(self):
        self.tracker.record_shadow_order("BTC", _order("BTC", 1.0, 1), run_id="r1")
        report = self.tracker.report()
        self.assertEqual(report["symbols_tracked"], 1)
        self.assertFalse(report["broker_execution"])
        self.assertIn("BTC", report["cycles"])
        events = read_tracker_audit(self.audit)
        self.assertTrue(events)
        self.assertTrue(all(event["research_only"] if "research_only" in event else True for event in events))

    def test_errors(self):
        with self.assertRaises(ValueError):
            self.tracker.demote("missing", "r", "x")
        with self.assertRaises(ValueError):
            self.tracker.recover("missing", "r", "x")


if __name__ == "__main__":
    unittest.main()
