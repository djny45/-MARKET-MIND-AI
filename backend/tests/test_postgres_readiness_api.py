import unittest
from unittest.mock import patch

from app.agent_council_api import postgres_readiness_api


class PostgresReadinessApiTests(unittest.TestCase):
    def test_route_returns_connectivity_probe_without_running_migrations(self):
        expected = {
            "status": "ready",
            "configured": True,
            "reachable": True,
            "driver": "psycopg",
        }
        with patch("app.agent_council_api.postgres_readiness", return_value=expected) as probe:
            result = postgres_readiness_api()
        self.assertEqual(result, expected)
        probe.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
