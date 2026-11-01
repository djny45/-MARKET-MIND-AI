import unittest
from app.market_event_quality import diagnose_market_events


def base(event_id, sequence, event_type="trade", payload=None, event_time="2026-10-31T10:00:00Z", received_at="2026-10-31T10:00:01Z"):
    return {"event_id": event_id, "sequence_number": sequence, "event_type": event_type,
            "provider": "p", "venue": "v", "instrument_id": "x",
            "event_time": event_time, "received_at": received_at, "payload": payload or {}}


class MarketEventQualityTests(unittest.TestCase):
    def test_sequence_gaps_duplicates_and_ordering(self):
        result = diagnose_market_events([base("a", 1), base("b", 4), base("c", 4), base("d", 2)])
        self.assertEqual(result["sequence_integrity"]["gap_count"], 1)
        self.assertEqual(result["sequence_integrity"]["duplicate_sequence_count"], 1)
        self.assertEqual(result["sequence_integrity"]["out_of_order_count"], 1)

    def test_snapshot_level_order_and_crossed_book(self):
        event = base("book", None, "order_book_snapshot", {
            "bids": [{"price": 100, "quantity": 2}, {"price": 101, "quantity": 1}],
            "asks": [{"price": 100, "quantity": 3}, {"price": 102, "quantity": 1}],
        })
        result = diagnose_market_events([event])
        issues = result["order_book_integrity"]["anomalies"][0]["issues"]
        self.assertIn("bids_not_descending", issues)
        self.assertIn("crossed_or_locked_snapshot", issues)

    def test_receive_before_event_and_invalid_time(self):
        result = diagnose_market_events([base("a", 1, event_time="bad", received_at="2026-10-31T09:00:00Z")])
        self.assertEqual(result["timestamp_integrity"]["invalid_timestamp_count"], 1)
        self.assertEqual(result["timestamp_integrity"]["received_before_event_count"], 0)

    def test_scope_isolated_by_provider(self):
        first = base("a", 1)
        second = base("b", 5)
        second["provider"] = "other"
        result = diagnose_market_events([first, second])
        self.assertEqual(result["sequence_integrity"]["gap_count"], 0)


if __name__ == "__main__":
    unittest.main()
