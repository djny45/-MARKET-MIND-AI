import os
import tempfile
import unittest
from unittest.mock import patch

from app.market_events import query_market_events, store_market_events


def event(event_type="trade", payload=None, event_id="trade-1"):
    return {
        "event_id": event_id, "instrument_id": "crypto:venue:BTCUSDT",
        "event_type": event_type, "provider": "test-provider", "venue": "TEST",
        "event_time": "2026-10-31T10:00:00Z",
        "received_at": "2026-10-31T10:00:01+00:00",
        "sequence_number": 1, "status": "historical", "currency": "USDT",
        "payload": payload or {"price": 60000, "quantity": 0.2, "side": "buy"},
    }


class HistoricalMarketEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "test.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_trade_import_query_and_provenance(self):
        result = store_market_events([event()])
        self.assertEqual(result["inserted"], 1)
        found = query_market_events(instrument_id="crypto:venue:BTCUSDT", event_type="trade")
        self.assertEqual(found["count"], 1)
        self.assertEqual(found["events"][0]["provider"], "test-provider")
        self.assertEqual(found["events"][0]["payload"]["side"], "buy")
        self.assertEqual(len(found["events"][0]["payload_sha256"]), 64)

    def test_idempotent_import_ignores_duplicate_provider_event(self):
        item = event()
        self.assertEqual(store_market_events([item])["inserted"], 1)
        result = store_market_events([item])
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["duplicates_ignored"], 1)

    def test_quote_validation_rejects_crossed_market(self):
        item = event("quote", {"bid_price": 101, "ask_price": 100, "bid_size": 1, "ask_size": 1}, "q-1")
        with self.assertRaises(ValueError):
            store_market_events([item])

    def test_order_book_snapshot_validation(self):
        payload = {"bids": [{"price": 100, "quantity": 2}], "asks": [{"price": 101, "quantity": 3}]}
        self.assertEqual(store_market_events([event("order_book_snapshot", payload, "ob-1")])["inserted"], 1)

    def test_event_types_validate_required_fields(self):
        cases = [
            ("open_interest", {"value": 5}),
            ("funding", {"rate": 0.01, "interval": "8h"}),
            ("fx_rate", {"rate": 1.1, "base": "EUR", "quote": "EUR", "rate_type": "reference"}),
        ]
        for kind, payload in cases:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                store_market_events([event(kind, payload, kind + "-1")])

    def test_timezone_is_mandatory_and_sequence_nonnegative(self):
        item = event()
        item["event_time"] = "2026-10-31T10:00:00"
        with self.assertRaises(ValueError):
            store_market_events([item])
        item = event()
        item["sequence_number"] = -1
        with self.assertRaises(ValueError):
            store_market_events([item])

    def test_query_time_range_and_validation(self):
        store_market_events([event()])
        self.assertEqual(query_market_events(start="2026-10-31T09:00:00Z")["count"], 1)
        with self.assertRaises(ValueError):
            query_market_events(start="2026-11-01T00:00:00Z", end="2026-10-01T00:00:00Z")
        with self.assertRaises(ValueError):
            query_market_events(limit=5001)


if __name__ == "__main__":
    unittest.main()
