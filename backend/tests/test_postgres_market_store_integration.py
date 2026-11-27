"""Real PostgreSQL integration coverage using an isolated CI service database."""
import os
import unittest
from datetime import datetime, timezone

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.postgres_market_migrations import apply_market_data_schema
from app import postgres_market_store as store


class PostgresMarketStoreIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ.get("MARKET_MIND_TEST_DATABASE_URL")
        if not cls.dsn:
            raise unittest.SkipTest("MARKET_MIND_TEST_DATABASE_URL is not configured")
        configured = {"DATABASE_URL": cls.dsn}
        migration = apply_market_data_schema(configured)
        if migration.get("status") != "ready":
            raise RuntimeError("isolated PostgreSQL schema migration failed")
        cls.environ = configured
        cls.symbol = "CI_PG_INTEGRATION"
        cls.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cls.retrieved_at = datetime.now(timezone.utc)

    @classmethod
    def tearDownClass(cls):
        if not getattr(cls, "dsn", None):
            return
        import psycopg
        with psycopg.connect(cls.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM market_ingestion_audit_events WHERE symbol=%s", (cls.symbol,))
                cursor.execute("DELETE FROM market_bars WHERE symbol=%s", (cls.symbol,))

    def test_migrate_write_read_lineage_audit_and_readiness(self):
        batch = MarketDataBatch(
            symbol=self.symbol,
            interval="1d",
            status=DataStatus.SYNTHETIC,
            source="synthetic-fixture",
            retrieved_at=self.retrieved_at,
            bars=[
                OHLCVBar(
                    timestamp=self.timestamp,
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=103.0,
                    volume=1200.0,
                )
            ],
        )
        stored = store.store_batch(batch, environ=self.environ)
        self.assertEqual(stored["stored"], 1)

        history = store.get_bars(self.symbol, "1d", environ=self.environ)
        self.assertEqual(history["count"], 1)
        self.assertEqual(history["bars"][0]["close"], 103.0)
        self.assertEqual(history["source"], "synthetic-fixture")

        lineage = store.get_data_lineage(self.symbol, "1d", environ=self.environ)
        self.assertEqual(lineage["observation_count"], 1)
        self.assertEqual(lineage["lineage"][0]["source"], "synthetic-fixture")

        audit = store.get_audit_events(self.symbol, "1d", environ=self.environ)
        self.assertEqual(audit["count"], 1)
        self.assertEqual(audit["events"][0]["event_type"], "market_data_batch_stored")

        readiness = store.database_readiness(environ=self.environ)
        self.assertEqual(readiness["status"], "ready")
        self.assertTrue(readiness["reachable"])
        self.assertTrue(readiness["writable"])


if __name__ == "__main__":
    unittest.main()
