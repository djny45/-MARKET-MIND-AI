import os
import tempfile
import unittest
from unittest.mock import patch

from app.analytical_agent_tasks import enqueue_research_task, list_recent_task_activity

class AgentNetworkActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "activity.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_recent_activity_snapshot_aggregates_task_states(self):
        queued = enqueue_research_task("worker_007", "network activity test")
        snapshot = list_recent_task_activity(limit=20)
        self.assertGreaterEqual(snapshot["task_count"], 1)
        self.assertEqual(snapshot["status_counts"]["queued"], 1)
        self.assertEqual(snapshot["latest_by_agent"]["worker_007"]["task_id"], queued["task_id"])
        self.assertEqual(snapshot["source"], "persisted_sqlite_task_records_and_audit_events")

    def test_recent_activity_includes_task_queued_audit_event(self):
        queued = enqueue_research_task("worker_008", "audit in activity view")
        snapshot = list_recent_task_activity(limit=20)
        matching = [event for event in snapshot["recent_audit_events"]
                    if event["task_id"] == queued["task_id"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["event_type"], "task_queued")
        self.assertEqual(snapshot["audit_event_count"], len(snapshot["recent_audit_events"]))

    def test_recent_activity_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            list_recent_task_activity(limit=0)
