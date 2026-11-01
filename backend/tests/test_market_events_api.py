import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import (HistoricalMarketEventsRequest, import_historical_market_events,
                      historical_market_events, historical_market_event_quality, historical_trade_flow)


class HistoricalMarketEventsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "test.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_import_and_query_historical_events(self):
        payload = {
            "event_id": "api-trade-1", "instrument_id": "india:nse:RELIANCE",
            "event_type": "trade", "provider": "csv-import", "venue": "NSE",
            "event_time": "2026-10-30T09:15:00+05:30",
            "received_at": "2026-10-30T10:00:00+05:30",
            "status": "historical", "payload": {"price": 1450, "quantity": 10, "side": "unknown"},
        }
        result = import_historical_market_events(HistoricalMarketEventsRequest(events=[payload]))
        self.assertEqual(result["inserted"], 1)
        found = historical_market_events("india:nse:RELIANCE", "trade", None, "NSE", None, None, 50)
        self.assertEqual(found["count"], 1)
        self.assertEqual(found["events"][0]["event_time"], "2026-10-30T03:45:00+00:00")

    def test_quality_endpoint_reports_sequence_gap(self):
        payloads = []
        for event_id, sequence in (("quality-1", 1), ("quality-3", 3)):
            payloads.append({
                "event_id": event_id, "instrument_id": "india:nse:RELIANCE",
                "event_type": "trade", "provider": "quality-test", "venue": "NSE",
                "event_time": "2026-10-30T09:15:00+05:30",
                "received_at": "2026-10-30T09:15:01+05:30",
                "sequence_number": sequence, "status": "historical",
                "payload": {"price": 1450, "quantity": 10, "side": "unknown"},
            })
        import_historical_market_events(HistoricalMarketEventsRequest(events=payloads))
        result = historical_market_event_quality(
            "india:nse:RELIANCE", "trade", "quality-test", "NSE", None, None, 50
        )
        self.assertEqual(result["sequence_integrity"]["gap_count"], 1)
        self.assertEqual(result["sampled_events"], 2)

    def test_trade_flow_api_withholds_cvd_for_unknown_side(self):
        payloads = []
        for event_id, minute, side, quantity in (
            ("flow-buy", "09:15:01", "buy", 5),
            ("flow-unknown", "09:15:20", "unknown", 3),
        ):
            payloads.append({
                "event_id": event_id, "instrument_id": "india:nse:RELIANCE",
                "event_type": "trade", "provider": "flow-test", "venue": "NSE",
                "event_time": f"2026-10-30T{minute}+05:30",
                "received_at": f"2026-10-30T{minute}+05:30",
                "status": "historical",
                "payload": {"price": 1450, "quantity": quantity, "side": side},
            })
        import_historical_market_events(HistoricalMarketEventsRequest(events=payloads))
        result = historical_trade_flow("india:nse:RELIANCE", 60, "flow-test", "NSE", None, None, 5000)
        self.assertFalse(result["cvd_available"])
        self.assertEqual(result["buckets"][0]["unknown_volume"], 3)
        self.assertIsNone(result["buckets"][0]["cumulative_volume_delta"])

    def test_invalid_event_returns_http_400(self):
        with self.assertRaises(HTTPException) as error:
            import_historical_market_events(HistoricalMarketEventsRequest(events=[{
                "event_id": "bad", "instrument_id": "X", "event_type": "quote",
                "provider": "p", "venue": "v", "event_time": "2026-10-30T09:15:00Z",
                "payload": {"bid_price": 10, "ask_price": 9, "bid_size": 1, "ask_size": 1},
            }]))
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
