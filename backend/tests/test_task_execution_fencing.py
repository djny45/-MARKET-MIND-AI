import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.analytical_agent_tasks import (
    enqueue_research_task,
    execute_queued_research_task,
    get_research_task,
    list_task_audit_events,
)


class ResearchTaskExecutionFencingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "tasks.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_stale_executor_cannot_overwrite_newer_claim_result(self):
        import sqlite3
        from app.analytical_agent_tasks import recover_interrupted_research_tasks

        queued = enqueue_research_task("worker_041", "exercise stale execution fencing")
        calls = {"count": 0, "new_attempt_result": None}

        def overlapping_synthesis(_payload):
            calls["count"] += 1
            if calls["count"] == 1:
                stale = (datetime.now(timezone.utc) - timedelta(seconds=1200)).isoformat()
                with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
                    db.execute(
                        "UPDATE analytical_agent_tasks SET updated_at=? WHERE task_id=?",
                        (stale, queued["task_id"]),
                    )
                recovery = recover_interrupted_research_tasks()
                self.assertEqual(recovery["requeued_interrupted_count"], 1)
                calls["new_attempt_result"] = execute_queued_research_task(queued["task_id"])
                return {"status": "completed", "summary": "stale attempt result"}

            return {"status": "completed", "summary": "newer attempt result"}

        with patch("app.analytical_agent_tasks.synthesize_research", side_effect=overlapping_synthesis):
            stale_attempt_result = execute_queued_research_task(queued["task_id"])

        saved = get_research_task(queued["task_id"])
        self.assertFalse(stale_attempt_result)
        self.assertTrue(calls["new_attempt_result"])
        self.assertEqual(calls["count"], 2)
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(
            saved["result"]["shared_core_result"]["summary"],
            "newer attempt result",
        )
        self.assertEqual(saved["execution_attempts"], 2)

        events = list_task_audit_events(queued["task_id"])["events"]
        event_types = [event["event_type"] for event in events]
        self.assertEqual(event_types.count("task_requeued"), 1)
        self.assertEqual(event_types.count("task_completed"), 1)


if __name__ == "__main__":
    unittest.main()
