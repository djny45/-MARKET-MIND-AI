import unittest
from app.trade_flow import build_trade_flow_buckets

class TradeFlowTests(unittest.TestCase):
    def trade(self, event_id, time, quantity, side):
        return {"event_id": event_id, "event_type": "trade", "event_time": time,
                "payload": {"quantity": quantity, "price": 10, "side": side}}

    def test_full_classification_builds_delta_and_cvd(self):
        events = [
            self.trade("1", "2026-10-30T09:15:01+00:00", 5, "buy"),
            self.trade("2", "2026-10-30T09:15:20+00:00", 2, "sell"),
            self.trade("3", "2026-10-30T09:16:01+00:00", 4, "buy"),
        ]
        result = build_trade_flow_buckets(events, 60)
        self.assertTrue(result["cvd_available"])
        self.assertEqual(result["buckets"][0]["known_side_delta"], 3)
        self.assertEqual(result["buckets"][1]["cumulative_volume_delta"], 7)

    def test_unknown_side_withholds_cvd(self):
        events = [
            self.trade("1", "2026-10-30T09:15:01+00:00", 5, "buy"),
            self.trade("2", "2026-10-30T09:15:20+00:00", 3, "unknown"),
        ]
        result = build_trade_flow_buckets(events, 60)
        self.assertFalse(result["cvd_available"])
        self.assertIsNone(result["buckets"][0]["cumulative_volume_delta"])
        self.assertEqual(result["buckets"][0]["unknown_volume"], 3)
        self.assertEqual(result["buckets"][0]["side_classification_coverage"], 0.625)

    def test_empty_sample_and_truncation_metadata(self):
        result = build_trade_flow_buckets([], 30, total_matching=20, limit=10)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["bucket_count"], 0)
        self.assertFalse(result["cvd_available"])

    def test_invalid_bucket_rejected(self):
        with self.assertRaises(ValueError):
            build_trade_flow_buckets([], 0)

if __name__ == "__main__":
    unittest.main()
