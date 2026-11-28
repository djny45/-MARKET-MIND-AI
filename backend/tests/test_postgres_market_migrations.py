import unittest

from app.postgres_market_migrations import (
    MARKET_DATA_SCHEMA_VERSION,
    apply_market_data_schema,
)


class PostgresMarketMigrationTests(unittest.TestCase):
    def test_missing_dsn_does_not_connect(self):
        called = False

        def connect(*_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("must not connect")

        result = apply_market_data_schema({}, connect=connect)
        self.assertEqual(result["status"], "not_configured")
        self.assertFalse(called)

    def test_applies_schema_under_transactional_lock(self):
        class Cursor:
            def __init__(self):
                self.statements = []
                self.last_query = ""
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def execute(self, query, params=None):
                self.last_query = query
                self.statements.append((query, params))
            def fetchone(self):
                if "COALESCE(MAX(version)" in self.last_query:
                    return (0,)
                return None

        class Connection:
            def __init__(self): self.cur = Cursor()
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def cursor(self): return self.cur

        connection = Connection()

        def connect(dsn, connect_timeout):
            self.assertEqual(dsn, "postgresql://example/db")
            self.assertEqual(connect_timeout, 3)
            return connection

        result = apply_market_data_schema(
            {"DATABASE_URL": "postgresql://example/db"}, connect=connect
        )
        self.assertEqual(result, {
            "status": "ready",
            "applied_version": MARKET_DATA_SCHEMA_VERSION,
        })
        sql = "\n".join(query for query, _ in connection.cur.statements)
        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS market_bars", sql)
        self.assertIn("market_ingestion_audit_events", sql)
        self.assertIn("INSERT INTO schema_migrations", sql)

    def test_dsn_and_exception_text_are_not_returned(self):
        def fail(*_args, **_kwargs):
            raise OSError("postgresql://private-secret failed")

        result = apply_market_data_schema(
            {"DATABASE_URL": "postgresql://private-secret/db"}, connect=fail
        )
        self.assertEqual(result["status"], "not_ready")
        self.assertEqual(result["error_type"], "OSError")
        self.assertNotIn("private-secret", repr(result))


if __name__ == "__main__":
    unittest.main()
