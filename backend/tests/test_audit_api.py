import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import audit_events, market_data_heatmap, market_data_lineage, market_data_overview, market_data_screener
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

    async def test_overview_route_reports_local_coverage_only(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 2)
                store_batch(batch)
                result = market_data_overview(100)
        self.assertEqual(result["instrument_interval_count"], 1)
        self.assertEqual(result["coverage"][0]["symbol"], "BTCUSD")


    async def test_heatmap_route_returns_stored_return_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 5)
                store_batch(batch)
                result = market_data_heatmap("1d", 100)
        self.assertEqual(result["status"], "stored_return_heatmap")
        self.assertEqual(result["cells"][0]["symbol"], "BTCUSD")
        self.assertEqual(result["cells"][0]["status"], "calculated")

    def test_heatmap_route_validates_interval_and_limit(self):
        with self.assertRaises(HTTPException) as interval_error:
            market_data_heatmap("5m", 100)
        self.assertEqual(interval_error.exception.status_code, 400)
        with self.assertRaises(HTTPException) as limit_error:
            market_data_heatmap("1d", 201)
        self.assertEqual(limit_error.exception.status_code, 400)

    async def test_screener_route_returns_coverage_filtered_stored_data(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 5)
                store_batch(batch)
                result = market_data_screener("1d", 100, 2)
        self.assertEqual(result["status"], "stored_data_screener")
        self.assertEqual(result["cells"][0]["symbol"], "BTCUSD")
        self.assertEqual(result["cells"][0]["observation_count"], 5)

    def test_screener_route_validates_interval_limit_and_coverage(self):
        for args in (("5m", 100, 2), ("1d", 201, 2), ("1d", 100, 0), ("1d", 100, 5001)):
            with self.subTest(args=args):
                with self.assertRaises(HTTPException) as error:
                    market_data_screener(*args)
                self.assertEqual(error.exception.status_code, 400)

    def test_overview_route_validates_limit(self):
        with self.assertRaises(HTTPException) as error:
            market_data_overview(501)
        self.assertEqual(error.exception.status_code, 400)

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
