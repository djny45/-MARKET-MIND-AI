import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.analytical_agent_tasks import (
    agent_supervisor_status,
    dispatch_queued_research_tasks,
    enqueue_research_task,
    execute_queued_research_task,
    get_research_task,
    recover_interrupted_research_tasks,
)


class AgentSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "supervisor.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_status_reports_persisted_task_counts(self):
        enqueue_research_task("worker_001", "queued sample")
        status = agent_supervisor_status()
        self.assertEqual(status["registered_agent_count"], 550)
        self.assertEqual(status["status_counts"]["queued"], 1)
        self.assertFalse(status["continuous_daemon"])
        self.assertFalse(status["distributed_queue"])

    def test_dispatch_executes_bounded_queue_snapshot(self):
        queued = enqueue_research_task("worker_001", "dispatch sample")
        result = dispatch_queued_research_tasks(limit=10, max_concurrency=2)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["dispatched"], 1)
        self.assertEqual(result["max_concurrency"], 1)
        task = get_research_task(queued["task_id"])
        self.assertEqual(task["status"], "completed")

    def test_duplicate_dispatch_claims_task_only_once(self):
        queued = enqueue_research_task("worker_004", "duplicate dispatch sample")
        with patch("app.analytical_agent_tasks.synthesize_research", return_value={"status": "completed"}) as synthesize:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(execute_queued_research_task, queued["task_id"])
                           for _ in range(2)]
                for future in futures:
                    future.result()
            self.assertEqual(synthesize.call_count, 1)
        self.assertEqual(get_research_task(queued["task_id"])["status"], "completed")

    def test_recovery_requeues_interrupted_tasks_without_dispatch(self):
        queued = enqueue_research_task("worker_002", "recover sample")
        import sqlite3
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute("UPDATE analytical_agent_tasks SET status='running' WHERE task_id=?",
                       (queued["task_id"],))
        result = recover_interrupted_research_tasks()
        self.assertEqual(result["requeued_interrupted_count"], 1)
        self.assertIn(queued["task_id"], result["queued_task_ids"])
        self.assertEqual(get_research_task(queued["task_id"])["status"], "queued")
        self.assertEqual(result["recovery_mode"], "manual_requeue_no_dispatch")

    def test_dispatch_bounds_are_validated(self):
        with self.assertRaises(ValueError):
            dispatch_queued_research_tasks(limit=0)
        with self.assertRaises(ValueError):
            dispatch_queued_research_tasks(max_concurrency=17)


if __name__ == "__main__":
    unittest.main()
