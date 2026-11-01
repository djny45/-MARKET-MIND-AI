import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import HistoricalMarketEventsRequest, import_historical_market_events, historical_market_events


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
