import unittest

from app.postgres import database_url, postgres_readiness


class PostgresReadinessTests(unittest.TestCase):
    def test_database_url_is_not_modified_or_exposed(self):
        self.assertEqual(
            database_url({"DATABASE_URL": "postgresql://example/db"}),
            "postgresql://example/db",
        )
        self.assertIsNone(database_url({"DATABASE_URL": "  "}))

    def test_missing_database_url_is_not_configured(self):
        result = postgres_readiness({})
        self.assertEqual(result["status"], "not_configured")
        self.assertFalse(result["reachable"])
        self.assertNotIn("url", result)

    def test_successful_probe(self):
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def execute(self, query): self.query = query
            def fetchone(self): return (1,)

        class Connection:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def cursor(self): return Cursor()

        def fake_connect(dsn, connect_timeout):
            self.assertEqual(dsn, "postgresql://secret/db")
            self.assertEqual(connect_timeout, 3)
            return Connection()

        result = postgres_readiness(
            {"DATABASE_URL": "postgresql://secret/db"}, connect=fake_connect
        )
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["reachable"])
        self.assertNotIn("secret", repr(result))

    def test_failure_redacts_exception_message_and_dsn(self):
        def fail_connect(*_args, **_kwargs):
            raise OSError("could not connect using postgresql://secret")

        result = postgres_readiness(
            {"DATABASE_URL": "postgresql://secret/db"}, connect=fail_connect
        )
        self.assertEqual(result["status"], "not_ready")
        self.assertEqual(result["error_type"], "OSError")
        self.assertNotIn("secret", repr(result))


if __name__ == "__main__":
    unittest.main()
