import os
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError


class AgentSupervisorRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "supervisor-routes.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_status_route_exposes_manual_supervisor_boundary(self):
        from app.main import analytical_agent_supervisor_status

        result = analytical_agent_supervisor_status()
        self.assertEqual(result["registered_agent_count"], 550)
        self.assertFalse(result["continuous_daemon"])
        self.assertFalse(result["distributed_queue"])

    def test_dispatch_route_rejects_out_of_range_limits(self):
        from app.main import (
            AgentSupervisorDispatchRequest,
            analytical_agent_supervisor_dispatch,
        )

        with self.assertRaises(ValidationError):
            request = AgentSupervisorDispatchRequest(limit=551, max_concurrency=4)
            analytical_agent_supervisor_dispatch(request)

    def test_recovery_route_requeues_but_does_not_dispatch(self):
        from app.analytical_agent_tasks import enqueue_research_task
        from app.main import analytical_agent_recover_tasks

        task = enqueue_research_task("worker_003", "route recovery test")
        import sqlite3
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_tasks SET status='running' WHERE task_id=?",
                (task["task_id"],),
            )

        result = analytical_agent_recover_tasks()
        self.assertEqual(result["requeued_interrupted_count"], 1)
        self.assertEqual(result["recovery_mode"], "manual_requeue_no_dispatch")
        self.assertIn(task["task_id"], result["queued_task_ids"])


if __name__ == "__main__":
    unittest.main()
