import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import provider_status, readiness
from app import market_store


class ServiceStatusTests(unittest.TestCase):
    def test_readiness_initializes_and_reports_local_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "status.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}):
                result = readiness()
            self.assertEqual(result["status"], "ready")
            self.assertTrue(result["checks"]["database"]["reachable"])
            self.assertTrue(result["checks"]["database"]["market_bars_schema"])
            self.assertEqual(result["checks"]["database"]["schema_version"], 1)
            self.assertFalse(result["execution"]["paper_trading"])
            self.assertFalse(result["execution"]["broker_execution"])

    def test_readiness_reports_database_failure_without_leaking_path(self):
        with patch("app.market_store.database_readiness", return_value={
            "status": "not_ready", "reachable": False,
            "market_bars_schema": False, "error": "OperationalError",
        }):
            with self.assertRaises(HTTPException) as error:
                readiness()
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail["checks"]["database"]["error"], "OperationalError")
        self.assertNotIn("database_path", error.exception.detail["checks"]["database"])

    def test_readiness_reports_write_ability_and_disk_headroom(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "status.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}, clear=False):
                result = readiness()
            self.assertTrue(result["checks"]["database"]["writable"])
            self.assertIn(result["checks"]["storage"]["status"], {"ok", "low"})
            self.assertGreater(result["checks"]["storage"]["free_bytes"], 0)
            self.assertNotIn(directory, result["checks"]["storage"],
                             "readiness must not leak the database path")

    def test_readiness_fails_when_the_volume_is_effectively_full(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "status.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database,
                                         "MARKET_MIND_DISK_MIN_FREE_MB": "100000000"}):
                with self.assertRaises(HTTPException) as error:
                    readiness()
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail["checks"]["storage"]["status"], "critical")
        self.assertTrue(error.exception.detail["checks"]["database"]["writable"])

    def test_readiness_stays_ready_while_disk_is_only_low(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "status.sqlite")
            usage = market_store.shutil.disk_usage(directory)
            threshold_mb = str(max(1, int(usage.free / (1024 * 1024) * 2)))
            with patch.dict(os.environ, {"MARKET_MIND_DB": database,
                                         "MARKET_MIND_DISK_MIN_FREE_MB": threshold_mb}):
                result = readiness()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["checks"]["storage"]["status"], "low")

    def test_readiness_fails_when_the_database_is_not_writable(self):
        with patch("app.market_store.database_readiness", return_value={
            "status": "not_ready", "reachable": True, "writable": False,
            "market_bars_schema": True, "schema_version": 1,
        }):
            with self.assertRaises(HTTPException) as error:
                readiness()
        self.assertEqual(error.exception.status_code, 503)
        self.assertFalse(error.exception.detail["checks"]["database"]["writable"])

    def test_provider_status_does_not_claim_live_data(self):
        result = provider_status()
        self.assertEqual(result["status"], "no_live_provider_configured")
        self.assertEqual(result["live_providers"], [])
        self.assertEqual(result["available_adapters"][0]["data_status"], "synthetic")


if __name__ == "__main__":
    unittest.main()
