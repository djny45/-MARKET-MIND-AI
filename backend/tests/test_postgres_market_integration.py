"""Real PostgreSQL integration coverage for the market-store foundation.

The CI workflow supplies MARKET_MIND_TEST_DATABASE_URL and a disposable
PostgreSQL service. Local runs skip cleanly when that variable is absent.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.postgres_market_migrations import apply_market_data_schema
from app import postgres_market_store as store


TEST_DSN = os.environ.get("MARKET_MIND_TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DSN, "requires disposable MARKET_MIND_TEST_DATABASE_URL")
class PostgresMarketStoreIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environ = {"DATABASE_URL": TEST_DSN}
        migration = apply_market_data_schema(cls.environ)
        if migration.get("status") != "ready":
            raise RuntimeError("PostgreSQL test schema migration failed")

    def test_migrate_write_read_lineage_audit_and_readiness(self):
        symbol = "IT" + uuid4().hex[:10].upper()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        batch = MarketDataBatch(
            symbol=symbol,
            interval="1h",
            status=DataStatus.SYNTHETIC,
            source="integration-test-fixture",
            retrieved_at=now,
            bars=[
                OHLCVBar(
                    timestamp=now - timedelta(hours=1),
                    open=100, high=105, low=99, close=103, volume=10,
                ),
                OHLCVBar(
                    timestamp=now,
                    open=103, high=108, low=102, close=107, volume=12,
                ),
            ],
        )
        try:
            stored = store.store_batch(batch, environ=self.environ)
            self.assertEqual(stored["stored"], 2)

            history = store.get_bars(symbol, "1h", 10, environ=self.environ)
            self.assertEqual(history["count"], 2)
            self.assertEqual(history["bars"][0]["close"], 103.0)
            self.assertEqual(history["bars"][1]["close"], 107.0)
            self.assertEqual(history["sources"], ["integration-test-fixture"])

            lineage = store.get_data_lineage(symbol, "1h", environ=self.environ)
            self.assertEqual(lineage["observation_count"], 2)
            self.assertEqual(lineage["lineage"][0]["source"], "integration-test-fixture")

            audit = store.get_audit_events(symbol, "1h", environ=self.environ)
            self.assertEqual(audit["count"], 1)
            self.assertEqual(audit["events"][0]["observation_count"], 2)

            overview = store.get_market_overview(environ=self.environ)
            self.assertTrue(any(item["symbol"] == symbol for item in overview["coverage"]))

            readiness = store.database_readiness(environ=self.environ)
            self.assertEqual(readiness["status"], "ready")
            self.assertTrue(readiness["reachable"])
            self.assertTrue(readiness["writable"])
        finally:
            with psycopg.connect(TEST_DSN, connect_timeout=3) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM market_ingestion_audit_events WHERE symbol=%s", (symbol,))
                    cursor.execute("DELETE FROM market_bars WHERE symbol=%s", (symbol,))


if __name__ == "__main__":
    unittest.main()
