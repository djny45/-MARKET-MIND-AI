import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.research_execution_simulator import SimulationLedger, SimulatedFill, OrderState


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class SimulationLedgerTests(unittest.TestCase):
    def test_deterministic_lifecycle_and_fee_arithmetic(self):
        ledger = SimulationLedger()
        order = ledger.create_order("o1", "idem-1", "2")
        ledger.transition(order.order_id, OrderState.ACKNOWLEDGED, NOW)
        ledger.transition(order.order_id, OrderState.PARTIALLY_FILLED, NOW,
                          SimulatedFill.create("1", "100", "0.01", "0.001"))
        ledger.transition(order.order_id, OrderState.FILLED, NOW,
                          SimulatedFill.create("1", "100", "0.01", "0.001"))
        snapshot = ledger.snapshot("o1")
        self.assertEqual(snapshot["state"], "FILLED")
        self.assertEqual(Decimal(snapshot["filled_quantity"]), Decimal("2"))
        self.assertEqual(Decimal(snapshot["gross_value"]), Decimal("200.2000"))
        self.assertEqual(Decimal(snapshot["fees"]), Decimal("2.002000"))
        self.assertEqual(snapshot, ledger.snapshot("o1"))

    def test_idempotency_key_returns_existing_order(self):
        ledger = SimulationLedger()
        first = ledger.create_order("o1", "same-key", 1)
        second = ledger.create_order("o2", "same-key", 3)
        self.assertIs(first, second)
        self.assertEqual(second.order_id, "o1")

    def test_rejects_invalid_state_transition(self):
        ledger = SimulationLedger()
        ledger.create_order("o1", "k1", 1)
        with self.assertRaisesRegex(ValueError, "invalid transition"):
            ledger.transition("o1", OrderState.FILLED, NOW, SimulatedFill.create(1, 1))

    def test_rejects_overfill_and_invalid_fill_total(self):
        ledger = SimulationLedger()
        ledger.create_order("o1", "k1", 1)
        ledger.transition("o1", OrderState.ACKNOWLEDGED, NOW)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            ledger.transition("o1", OrderState.FILLED, NOW, SimulatedFill.create(2, 10))

    def test_rejects_naive_event_timestamp(self):
        ledger = SimulationLedger()
        ledger.create_order("o1", "k1", 1)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            ledger.transition("o1", OrderState.ACKNOWLEDGED, datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
