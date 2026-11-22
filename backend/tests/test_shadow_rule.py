import datetime
import tempfile
import unittest
from pathlib import Path

from app.research_shadow_session import ShadowSessionEngine, make_backtest_config
from app.shadow_rule import ShadowRuleEngine
from app.shadow_tracker import ShadowTracker


def _order(pnl, day):
    return {
        "symbol": "BTC",
        "side": "BUY" if pnl >= 0 else "SELL",
        "quantity": 1.0,
        "reference_price": 100.0,
        "expected_pnl": pnl,
        "timestamp": f"2026-11-{day:02d}T09:00:00",
    }


class ShadowRuleEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        audit = Path(self.tmp.name) / "tracker.jsonl"
        self.engine = ShadowRuleEngine(tracker=ShadowTracker(ShadowSessionEngine(make_backtest_config()), audit_path=audit))

    def tearDown(self):
        self.tmp.cleanup()

    def _register_and_age(self, symbol="BTC", hours=25):
        self.engine.register_strategy(symbol)
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
        self.engine.registered_at[symbol] = past.isoformat()

    def test_register_and_eligibility_shape(self):
        report = self.engine.register_strategy("BTC")
        self.assertEqual(report, "BTC")
        eligibility = self.engine.promotion_eligibility("BTC")
        self.assertEqual(eligibility["requires_human_approval"], True)
        self.assertEqual(eligibility["eligible_for_review"], False)

    def test_eligibility_requires_24h_and_minimum_cycles(self):
        self._register_and_age(hours=25)
        for day in range(1, 4):
            self.engine.tracker.record_shadow_order("BTC", _order(1.0, day), run_id="r1")
        eligibility = self.engine.promotion_eligibility("BTC")
        self.assertGreaterEqual(eligibility["hours_elapsed"], 24)
        self.assertGreaterEqual(eligibility["evaluation_cycles"], 3)
        self.assertTrue(eligibility["eligible_for_review"])

    def test_failed_cycles_block_eligibility(self):
        self._register_and_age(hours=25)
        self.engine.tracker.record_shadow_order("BTC", _order(1.0, 1), run_id="r1")
        self.engine.tracker.record_shadow_order("BTC", _order(-2.0, 2), run_id="r1")
        self.engine.tracker.record_shadow_order("BTC", _order(1.0, 3), run_id="r1")
        self.engine.tracker.record_shadow_order("BTC", _order(1.0, 4), run_id="r1")
        eligibility = self.engine.promotion_eligibility("BTC")
        self.assertEqual(eligibility["failed_cycles"], 1)
        self.assertFalse(eligibility["eligible_for_review"])

    def test_hours_elapsed_under_24(self):
        self.engine.register_strategy("BTC")
        self.assertLess(self.engine.hours_elapsed("BTC"), 24.0)

    def test_isolation_and_report(self):
        self.engine.register_strategy("BTC")
        self.engine.tracker.record_shadow_order("BTC", _order(1.0, 1), run_id="r1")
        self.engine.tracker.record_shadow_order("BTC", _order(1.0, 1), run_id="r2")
        report = self.engine.report()
        self.assertEqual(report["eligible_for_review"], [])
        self.assertTrue(report["research_only"])
        self.assertFalse(report["broker_execution"])

    def test_unknown_symbol(self):
        with self.assertRaises(ValueError):
            self.engine.promotion_eligibility("BTC")


if __name__ == "__main__":
    unittest.main()
