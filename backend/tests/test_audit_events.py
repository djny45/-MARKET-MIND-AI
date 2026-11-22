import concurrent.futures
import unittest

from app.audit_events import (
    EVENT_TYPES,
    REDACTED,
    AuditEventAggregator,
    redact,
)


class AuditEventTests(unittest.TestCase):
    def setUp(self):
        self.log = AuditEventAggregator(capacity=10)

    def test_event_has_required_fields_and_timestamp(self):
        event = self.log.record(
            "authorization",
            {"username": "alice", "role": "analyst"},
            "layout-1",
            "read",
            "success",
            metadata={"reason": "allowed"},
        )
        as_dict = event.__dict__
        for field in ("event_id", "event_type", "actor", "actor_role", "resource", "action", "outcome", "timestamp"):
            self.assertIn(field, as_dict)
        self.assertEqual(event.actor, "alice")
        self.assertEqual(event.actor_role, "analyst")
        self.assertEqual(event.outcome, "success")
        self.assertIn("T", event.timestamp)
        self.assertEqual(self.log.count(), 1)

    def test_recent_returns_newest_first_and_filters(self):
        self.log.record("authentication", None, "login", "post", "success")
        self.log.record("authorization", "alice", "layout-1", "read", "denied")
        self.log.record("authorization", "alice", "layout-2", "read", "success")
        denied = self.log.recent(event_type="authorization", outcome="denied")
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0]["resource"], "layout-1")
        self.assertEqual(self.log.recent(limit=2)[0]["resource"], "layout-2")
        self.assertEqual(self.log.recent(actor="alice")[0]["resource"], "layout-2")

    def test_capacity_is_bounded(self):
        for index in range(20):
            self.log.record("security", None, f"r{index}", "check", "info")
        self.assertEqual(self.log.count(), 10)
        self.assertEqual(self.log.recent(limit=10)[0]["resource"], "r19")

    def test_secrets_are_redacted_everywhere(self):
        secret = "super-secret-token-value"
        event = self.log.record(
            "authentication",
            {"username": "alice", "role": "admin", "api_key": secret},
            {"token": secret, "resource": "layout-1"},
            "login",
            "success",
            metadata={
                "password": secret,
                "authorization": f"Bearer {secret}",
                "nested": [{"csrf_token": secret, "safe": "ok"}],
            },
        )
        rendered = str(event)
        self.assertNotIn(secret, rendered)
        self.assertEqual(event.metadata["password"], REDACTED)
        self.assertEqual(event.metadata["nested"][0]["csrf_token"], REDACTED)
        self.assertEqual(event.metadata["nested"][0]["safe"], "ok")
        self.assertEqual(event.metadata["authorization"], REDACTED)

    def test_redact_handles_non_string_values(self):
        result = redact({"count": 3, "flag": True, "nothing": None, "secret": "x"})
        self.assertEqual(result["count"], 3)
        self.assertTrue(result["flag"])
        self.assertIsNone(result["nothing"])
        self.assertEqual(result["secret"], REDACTED)

    def test_unknown_event_type_or_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            self.log.record("not-a-type", None, "r", "a", "success")
        with self.assertRaises(ValueError):
            self.log.record("security", None, "r", "a", "not-an-outcome")
        with self.assertRaises(ValueError):
            self.log.recent(limit=0)
        self.assertIn("authorization", EVENT_TYPES)

    def test_concurrent_appends_are_lossless(self):
        def append(index):
            return self.log.record("security", None, f"r{index}", "check", "info")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            events = list(pool.map(append, range(10)))
        self.assertEqual(len({event.event_id for event in events}), 10)
        self.assertEqual(self.log.count(), 10)


if __name__ == "__main__":
    unittest.main()
