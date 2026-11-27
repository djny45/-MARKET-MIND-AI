"""Behavioral parity checks between SQLite and PostgreSQL market stores.

Runs against a disposable PostgreSQL database in CI and a temporary SQLite
file. It compares public response contracts, not database implementation
details. No managed/user database is touched by this test.
"""
import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from app.market_data import SyntheticFixtureAdapter
from app import market_store as sqlite_store
from app import postgres_market_store as postgres_store
from app.postgres_market_migrations import apply_market_data_schema


TEST_DSN = os.environ.get("MARKET_MIND_TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DSN, "requires disposable MARKET_MIND_TEST_DATABASE_URL")
class MarketStoreParityTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg_env = {"DATABASE_URL": TEST_DSN}
        result = apply_market_data_schema(cls.pg_env)
        if result != {"status": "ready", "applied_version": 1}:
            raise RuntimeError("PostgreSQL parity-test schema is not ready")

    async def test_sqlite_and_postgres_expose_matching_market_store_contract(self):
        symbol = "PT" + uuid4().hex[:10].upper()
        batch = await SyntheticFixtureAdapter().get_bars(symbol, "1d", 4)
        second_source = batch.model_copy(update={"source": "secondary-fixture"})

        with tempfile.TemporaryDirectory() as directory:
            sqlite_path = os.path.join(directory, "parity.sqlite")
            sqlite_env = {"MARKET_MIND_DB": sqlite_path}
            try:
                with patch.dict(os.environ, sqlite_env, clear=False):
                    sqlite_write = sqlite_store.store_batch(batch)
                    sqlite_second_write = sqlite_store.store_batch(second_source)
                    sqlite_history = sqlite_store.get_bars(symbol, "1d", 20)
                    sqlite_lineage = sqlite_store.get_data_lineage(symbol, "1d")
                    sqlite_audit = sqlite_store.get_audit_events(symbol, "1d", 20)
                    sqlite_overview = sqlite_store.get_market_overview(200)

                pg_write = postgres_store.store_batch(batch, environ=self.pg_env)
                pg_second_write = postgres_store.store_batch(second_source, environ=self.pg_env)
                pg_history = postgres_store.get_bars(symbol, "1d", 20, environ=self.pg_env)
                pg_lineage = postgres_store.get_data_lineage(symbol, "1d", environ=self.pg_env)
                pg_audit = postgres_store.get_audit_events(symbol, "1d", 20, environ=self.pg_env)
                pg_overview = postgres_store.get_market_overview(200, environ=self.pg_env)

                for sqlite_result, pg_result in (
                    (sqlite_write, pg_write),
                    (sqlite_second_write, pg_second_write),
                ):
                    for field in (
                        "stored", "symbol", "interval", "source", "status",
                        "first_timestamp", "last_timestamp", "ordering",
                        "duplicate_timestamps",
                    ):
                        self.assertEqual(sqlite_result[field], pg_result[field], field)

                self.assertEqual(sqlite_history, pg_history)
                self.assertEqual(sqlite_lineage, pg_lineage)
                self.assertEqual(sqlite_audit["count"], pg_audit["count"])
                self.assertEqual(
                    [
                        {key: event[key] for key in (
                            "event_type", "symbol", "interval", "source", "status",
                            "observation_count", "first_timestamp", "last_timestamp",
                        )}
                        for event in sqlite_audit["events"]
                    ],
                    [
                        {key: event[key] for key in (
                            "event_type", "symbol", "interval", "source", "status",
                            "observation_count", "first_timestamp", "last_timestamp",
                        )}
                        for event in pg_audit["events"]
                    ],
                )
                sqlite_coverage = next(
                    row for row in sqlite_overview["coverage"] if row["symbol"] == symbol
                )
                pg_coverage = next(
                    row for row in pg_overview["coverage"] if row["symbol"] == symbol
                )
                self.assertEqual(sqlite_coverage, pg_coverage)
            finally:
                with psycopg.connect(TEST_DSN, connect_timeout=3) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM market_ingestion_audit_events WHERE symbol=%s",
                            (symbol,),
                        )
                        cursor.execute("DELETE FROM market_bars WHERE symbol=%s", (symbol,))


if __name__ == "__main__":
    unittest.main()
