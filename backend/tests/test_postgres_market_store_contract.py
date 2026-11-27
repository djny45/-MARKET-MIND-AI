"""Contract-level parity checks for the PostgreSQL market-store adapter.

These tests exercise response shape, filters, bounds, and timestamp normalization
without requiring a database. Real PostgreSQL behavior is covered separately.
"""
import unittest
from datetime import datetime, timezone

from app import postgres_market_store as store


class Cursor:
    def __init__(self, *, rows=None):
        self.rows = list(rows or [])
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


class PostgresMarketStoreContractTests(unittest.TestCase):
    def connect(self, cursor):
        connection = Connection(cursor)
        return lambda *_args, **_kwargs: connection

    def test_audit_filters_and_limit_match_store_contract(self):
        occurred = datetime(2026, 1, 2, tzinfo=timezone.utc)
        cursor = Cursor(rows=[{
            "id": 7, "event_type": "market_data_batch_stored",
            "symbol": "BTCUSD", "interval": "1h", "source": "fixture",
            "status": "synthetic", "observation_count": 2,
            "first_timestamp": occurred, "last_timestamp": occurred,
            "occurred_at": occurred,
        }])
        result = store.get_audit_events(
            "btcusd", "1h", 999,
            environ={"DATABASE_URL": "postgresql://test/db"},
            connect=self.connect(cursor),
        )
        query, params = cursor.calls[0]
        self.assertIn("WHERE symbol = %s AND interval = %s", query)
        self.assertEqual(params, ("BTCUSD", "1h", 500))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["events"][0]["occurred_at"], occurred.isoformat())
        self.assertEqual(result["limit"], 500)
        self.assertNotIn("close", result["events"][0])

    def test_lineage_normalizes_timestamps_and_reports_bounded_limit(self):
        stamp = datetime(2026, 1, 3, tzinfo=timezone.utc)
        cursor = Cursor(rows=[{
            "source": "fixture", "status": "synthetic",
            "observation_count": 4, "first_timestamp": stamp,
            "last_timestamp": stamp, "latest_retrieval": stamp,
        }])
        result = store.get_data_lineage(
            "ethusd", "1d", 99999,
            environ={"DATABASE_URL": "postgresql://test/db"},
            connect=self.connect(cursor),
        )
        self.assertEqual(cursor.calls[0][1], ("ETHUSD", "1d", 5000))
        self.assertEqual(result["symbol"], "ETHUSD")
        self.assertEqual(result["observation_count"], 4)
        self.assertEqual(result["lineage"][0]["latest_retrieval"], stamp.isoformat())
        self.assertEqual(result["limit"], 5000)

    def test_overview_normalizes_postgres_arrays_and_timestamps(self):
        stamp = datetime(2026, 1, 4, tzinfo=timezone.utc)
        cursor = Cursor(rows=[{
            "symbol": "BTCUSD", "interval": "1d",
            "observation_count": 3, "distinct_timestamp_count": 2,
            "source_count": 2, "sources": ["fixture-a", "fixture-b"],
            "statuses": ["historical", "synthetic"],
            "first_timestamp": stamp, "last_timestamp": stamp,
            "latest_retrieval": stamp,
        }])
        result = store.get_market_overview(
            999,
            environ={"DATABASE_URL": "postgresql://test/db"},
            connect=self.connect(cursor),
        )
        self.assertEqual(cursor.calls[0][1], (500,))
        row = result["coverage"][0]
        self.assertEqual(row["sources"], ["fixture-a", "fixture-b"])
        self.assertEqual(row["statuses"], ["historical", "synthetic"])
        self.assertEqual(row["latest_retrieval"], stamp.isoformat())
        self.assertIn("not a live quote", result["data_note"])

    def test_bar_history_clamps_limit_to_contract_maximum(self):
        cursor = Cursor(rows=[])
        result = store.get_bars(
            "btcusd", "1d", 99999,
            environ={"DATABASE_URL": "postgresql://test/db"},
            connect=self.connect(cursor),
        )
        self.assertEqual(cursor.calls[0][1], ("BTCUSD", "1d", 5000))
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["bars"], [])
        self.assertEqual(result["source"], None)


if __name__ == "__main__":
    unittest.main()
