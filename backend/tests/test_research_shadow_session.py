import json
import tempfile
import unittest
from pathlib import Path

from app.research_shadow_session import (
    ShadowSessionEngine,
    make_backtest_config,
    replay_audit_log,
    shadow_metrics_from_log,
)


class ShadowSessionEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "shadow.jsonl"
        self.engine = ShadowSessionEngine(make_backtest_config(), log_path=self.log)
        self.engine.begin_run("run-1")

    def tearDown(self):
        self.tmp.cleanup()

    def _order(self, symbol="BTCUSDT", side="BUY", pnl=10.0, timestamp="2026-11-22T09:00"):
        return {
            "symbol": symbol,
            "side": side,
            "quantity": 1.5,
            "reference_price": 100.0,
            "notional": 150.0,
            "cost": 1.5,
            "expected_pnl": pnl,
            "rationale": "hypothesis: momentum edge",
            "timestamp": timestamp,
        }

    def test_orders_are_recorded_as_shadow_only(self):
        order = self.engine.record_shadow_order(self._order(), run_id="run-1")
        self.assertIsNotNone(order.id)
        self.assertFalse(order.as_record()["executed"])
        self.assertEqual(order.as_record()["mode"], "shadow_log_only")
        self.assertTrue(order.as_record()["research_only"])

    def test_record_rejects_invalid_orders(self):
        for bad in (
            {},
            {"symbol": "X", "quantity": 1, "reference_price": 1, "timestamp": "t"},
            {"symbol": "X", "side": "HOLD", "quantity": 1, "reference_price": 1, "timestamp": "t"},
            {"symbol": "X", "side": "BUY", "quantity": -1, "reference_price": 1, "timestamp": "t"},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.engine.record_shadow_order(bad, run_id="run-1")

    def test_list_orders_and_metrics(self):
        self.engine.record_shadow_order(self._order(), run_id="run-1")
        self.engine.record_shadow_order(self._order(side="SELL", pnl=-5.0, timestamp="2026-11-22T09:05"), run_id="run-1")
        orders = self.engine.list_orders("run-1")
        self.assertEqual(len(orders), 2)
        metrics = self.engine.metrics("run-1")
        self.assertEqual(metrics["executed_orders"], 0)
        self.assertGreater(metrics["gross_pnl"], 0)
        self.assertEqual(metrics["broker_execution"], False)

    def test_audit_log_is_persisted_and_replayed(self):
        self.engine.record_shadow_order(self._order(), run_id="run-1")
        self.assertEqual(len(replay_audit_log(self.log)), 1)
        persisted = json.loads(self.log.read_text().splitlines()[0])
        self.assertEqual(persisted["mode"], "shadow_log_only")
        aggregated = shadow_metrics_from_log(self.log)
        self.assertEqual(aggregated["shadow_orders"], 1)
        self.assertEqual(aggregated["executed_orders"], 0)
        self.assertFalse(aggregated["broker_execution"])

    def test_begin_run_resets_ids(self):
        self.engine.begin_run("run-2")
        order = self.engine.record_shadow_order(self._order(), run_id="run-2")
        self.assertEqual(order.id, 0)

    def test_record_rejects_non_finite_and_boolean_numbers(self):
        for field, value in (
            ("quantity", float("nan")),
            ("quantity", float("inf")),
            ("reference_price", float("-inf")),
            ("cost", float("nan")),
            ("expected_pnl", float("inf")),
            ("quantity", True),
        ):
            with self.subTest(field=field, value=value):
                order = self._order()
                order[field] = value
                with self.assertRaises(ValueError):
                    self.engine.record_shadow_order(order, run_id="run-1")

    def test_record_rejects_invalid_numeric_ranges(self):
        for field, value in (
            ("quantity", -0.01),
            ("reference_price", 0),
            ("notional", -1),
            ("cost", -0.01),
        ):
            with self.subTest(field=field, value=value):
                order = self._order()
                order[field] = value
                with self.assertRaises(ValueError):
                    self.engine.record_shadow_order(order, run_id="run-1")

    def test_record_rejects_blank_identifiers_and_text_fields(self):
        for order in (
            self._order(symbol=" "),
            {**self._order(), "timestamp": " "},
            {**self._order(), "side": []},
        ):
            with self.subTest(order=order):
                with self.assertRaises(ValueError):
                    self.engine.record_shadow_order(order, run_id="run-1")
        with self.assertRaises(ValueError):
            self.engine.record_shadow_order(self._order(), run_id=" ")
        with self.assertRaises(ValueError):
            self.engine.record_shadow_order([], run_id="run-1")


if __name__ == "__main__":
    unittest.main()
