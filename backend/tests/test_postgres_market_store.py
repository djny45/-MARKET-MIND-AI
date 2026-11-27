import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app import postgres_market_store as store


class FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, query, params=None): self.calls.append((query, params))
    def executemany(self, query, rows): self.calls.append((query, list(rows)))
    def fetchone(self): return self.fetchone_values.pop(0) if self.fetchone_values else None
    def fetchall(self): return self.fetchall_values.pop(0) if self.fetchall_values else []


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.rolled_back = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return self.fake_cursor
    def rollback(self): self.rolled_back = True


class PostgresMarketStoreTests(unittest.TestCase):
    def test_missing_dsn_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "postgres_not_configured"):
            with store._connection({}):
                pass

    def test_store_batch_upserts_and_audits_in_one_transaction(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        bar = SimpleNamespace(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            open=10.0, high=11.0, low=9.0, close=10.5, volume=12.0,
        )
        batch = SimpleNamespace(
            bars=[bar], symbol="BTCUSD", interval="1d",
            status=SimpleNamespace(value="synthetic"), source="synthetic-fixture",
            retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        result = store.store_batch(
            batch, environ={"DATABASE_URL": "postgresql://test/db"},
            connect=lambda *_args, **_kwargs: connection,
        )
        self.assertEqual(result["stored"], 1)
        self.assertEqual(result["symbol"], "BTCUSD")
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn("ON CONFLICT", cursor.calls[0][0])
        self.assertIn("market_ingestion_audit_events", cursor.calls[1][0])

    def test_get_bars_normalizes_datetimes_and_order(self):
        newer = datetime(2026, 1, 2, tzinfo=timezone.utc)
        older = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [
            {"timestamp": newer, "open": 2, "high": 3, "low": 1, "close": 2,
             "volume": 5, "status": "synthetic", "source": "fixture", "retrieved_at": newer},
            {"timestamp": older, "open": 1, "high": 2, "low": 1, "close": 2,
             "volume": 4, "status": "synthetic", "source": "fixture", "retrieved_at": newer},
        ]
        connection = FakeConnection(FakeCursor(fetchall_values=[rows]))
        result = store.get_bars(
            "btcusd", "1d", environ={"DATABASE_URL": "postgresql://test/db"},
            connect=lambda *_args, **_kwargs: connection,
        )
        self.assertEqual(result["symbol"], "BTCUSD")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["bars"][0]["timestamp"], older.isoformat())
        self.assertEqual(result["bars"][1]["timestamp"], newer.isoformat())

    def test_readiness_rolls_back_write_probe(self):
        cursor = FakeCursor(fetchone_values=[{"to_regclass": "market_bars"}, {"schema_version": 1}, {"?column?": 1}])
        connection = FakeConnection(cursor)
        result = store.database_readiness(
            environ={"DATABASE_URL": "postgresql://test/db"},
            connect=lambda *_args, **_kwargs: connection,
        )
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["writable"])
        self.assertTrue(connection.rolled_back)
        self.assertIn("__READINESS_PROBE__", cursor.calls[-1][0])

    def test_managed_database_has_no_local_disk_claim(self):
        result = store.storage_headroom()
        self.assertEqual(result["status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
