import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import audit_events, market_data_lineage
from app.market_data import SyntheticFixtureAdapter
from app.market_store import store_batch


class AuditApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_audit_and_lineage_routes_return_ingestion_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 2)
                store_batch(batch)
                audit = audit_events("BTCUSD", "1d", 10)
                lineage = market_data_lineage("BTCUSD", "1d", 5000)
        self.assertEqual(audit["count"], 1)
        self.assertEqual(audit["events"][0]["event_type"], "market_data_batch_stored")
        self.assertEqual(lineage["observation_count"], 2)
        self.assertEqual(lineage["lineage"][0]["status"], "synthetic")

    def test_audit_route_rejects_invalid_filters(self):
        with self.assertRaises(HTTPException) as symbol_error:
            audit_events(" ", None, 10)
        self.assertEqual(symbol_error.exception.status_code, 400)
        with self.assertRaises(HTTPException) as interval_error:
            audit_events(None, "5m", 10)
        self.assertEqual(interval_error.exception.status_code, 400)
        with self.assertRaises(HTTPException) as limit_error:
            audit_events(None, None, 501)
        self.assertEqual(limit_error.exception.status_code, 400)

    def test_lineage_route_rejects_invalid_scope(self):
        with self.assertRaises(HTTPException) as error:
            market_data_lineage("BTCUSD", "5m", 100)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
