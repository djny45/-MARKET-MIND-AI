import os
import tempfile
import unittest
from unittest.mock import patch

from app.trade_event_store import (
    list_trade_event_imports, persist_trade_event_import, query_trade_events,
)


class TradeEventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "trade.sqlite")})
        self.env.start()
        self.events = [{
            "event_id": "fill-1", "event_time": "2026-11-01T10:00:00+05:30",
            "instrument": "BTCUSDT", "event_type": "FILL", "side": "BUY",
            "quantity": "0.2500", "price": "65000.10", "fee": "0.01",
            "fee_currency": "USDT", "order_reference": "order-22", "source_row": 2,
        }]
        self.manifest = {
            "status": "dry_run_only", "persistence": "not_performed",
            "sha256": "a" * 64, "parser_version": "trade-event-csv-v2",
            "mapping": {"event_id": "id", "event_time": "time"},
            "bytes": 256, "total_rows": 1, "accepted_rows": 1,
            "rejected_rows": 0, "duplicate_rows": 0,
            "first_event_time": "2026-11-01T04:30:00+00:00",
            "last_event_time": "2026-11-01T04:30:00+00:00",
        }

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_persist_is_atomic_and_decimal_text_is_preserved(self):
        result = persist_trade_event_import(self.manifest, self.events)
        self.assertEqual(result["status"], "imported")
        found = query_trade_events(result["import_id"])
        self.assertEqual(found["count"], 1)
        row = found["events"][0]
        self.assertEqual(row["event_time"], "2026-11-01T04:30:00+00:00")
        self.assertEqual(row["quantity"], "0.2500")
        self.assertEqual(row["price"], "65000.10")
        self.assertEqual(row["fee_currency"], "USDT")
        self.assertEqual(row["order_reference"], "order-22")

    def test_duplicate_import_is_idempotent(self):
        first = persist_trade_event_import(self.manifest, self.events)
        second = persist_trade_event_import(self.manifest, self.events)
        self.assertEqual(second["status"], "already_imported")
        self.assertEqual(second["import_id"], first["import_id"])
        self.assertEqual(second["inserted_rows"], 0)
        self.assertEqual(list_trade_event_imports()["count"], 1)

    def test_invalid_later_row_rolls_back_entire_import(self):
        invalid = [self.events[0], {**self.events[0], "event_id": "bad-fill", "price": None, "source_row": 3}]
        manifest = {**self.manifest, "total_rows": 2, "accepted_rows": 2}
        with self.assertRaises(ValueError):
            persist_trade_event_import(manifest, invalid)
        self.assertEqual(list_trade_event_imports()["count"], 0)

    def test_refuses_activation_of_wrong_manifest_or_mismatched_rows(self):
        with self.assertRaises(ValueError):
            persist_trade_event_import({**self.manifest, "persistence": "already_done"}, self.events)
        with self.assertRaises(ValueError):
            persist_trade_event_import(self.manifest, [])

    def test_rejects_unsupported_event_types_and_bad_sides(self):
        for change in ({"event_type": "SUBMITTED"}, {"side": "LONG"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                persist_trade_event_import(self.manifest, [{**self.events[0], **change}])


if __name__ == "__main__":
    unittest.main()
