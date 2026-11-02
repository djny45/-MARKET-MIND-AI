import os
import tempfile
import unittest
from unittest.mock import patch

from app.analytical_agent_tasks import submit_research_task, get_research_task, list_research_tasks
from app.intelligence_core import synthesize_research

class AnalyticalAgentTaskTests(unittest.TestCase):
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

    def test_task_is_persisted_and_scoped_to_worker(self):
        result = submit_research_task("worker_001", "Review this supplied dataset", {"prices": [10, 11, 12]})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["worker_id"], "worker_001")
        self.assertEqual(result["execution_mode"], "bounded_synchronous_shared_core")
        saved = get_research_task(result["task_id"])
        self.assertEqual(saved["input"]["brief"], "Review this supplied dataset")
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["brain_context_sha256"], result["result"]["brain_context_sha256"])
        self.assertEqual(list_research_tasks("worker_001")["total"], 1)
        self.assertEqual(list_research_tasks("worker_002")["total"], 0)

    def test_task_without_configured_provider_is_explicit(self):
        result = submit_research_task("worker_003", "Summarize provided facts", {"facts": ["A", "B"]})
        self.assertEqual(result["result"]["shared_core_result"]["status"], "not_configured")
        self.assertEqual(result["result"]["result_mode"], "provider_unavailable_or_not_configured")

    def test_rejects_unknown_worker_and_oversized_brief(self):
        with self.assertRaises(ValueError):
            submit_research_task("worker_9999", "Brief")
        with self.assertRaises(ValueError):
            submit_research_task("worker_001", "x" * 4001)

    def test_rejects_non_json_data(self):
        with self.assertRaises(ValueError):
            submit_research_task("worker_001", "Brief", {"bad": object()})

    def test_unknown_task_returns_none(self):
        self.assertIsNone(get_research_task("not-a-task-id"))

    def test_queue_task_persists_queued_record_and_executes(self):
        from app.analytical_agent_tasks import enqueue_research_task, execute_queued_research_task
        queued = enqueue_research_task("worker_004", "Analyze provided metrics", {"metric": 7})
        self.assertEqual(queued["status"], "queued")
        saved = get_research_task(queued["task_id"])
        self.assertEqual(saved["status"], "queued")
        execute_queued_research_task(queued["task_id"])
        saved = get_research_task(queued["task_id"])
        self.assertIn(saved["status"], ("completed", "failed"))
        self.assertNotEqual(saved["status"], "queued")

    def test_queue_task_rejects_invalid_worker(self):
        from app.analytical_agent_tasks import enqueue_research_task
        with self.assertRaises(ValueError):
            enqueue_research_task("worker_9999", "Invalid worker")



    def test_recovery_requeues_running_tasks_and_preserves_queued(self):
        from app.analytical_agent_tasks import enqueue_research_task, recover_interrupted_research_tasks
        queued = enqueue_research_task("worker_005", "recover me")
        import sqlite3
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute("UPDATE analytical_agent_tasks SET status='running' WHERE task_id=?", (queued["task_id"],))
        recovery = recover_interrupted_research_tasks()
        self.assertEqual(recovery["requeued_interrupted_count"], 1)
        self.assertEqual(recovery["recovery_mode"], "manual_requeue_no_dispatch")
        self.assertEqual(get_research_task(queued["task_id"])["status"], "queued")

    def test_duplicate_dispatch_only_claims_once(self):
        from app.analytical_agent_tasks import enqueue_research_task, execute_queued_research_task
        queued = enqueue_research_task("worker_006", "single claim")
        execute_queued_research_task(queued["task_id"])
        first = get_research_task(queued["task_id"])
        execute_queued_research_task(queued["task_id"])
        second = get_research_task(queued["task_id"])
        self.assertEqual(first["status"], second["status"])
        self.assertEqual(first["updated_at"], second["updated_at"])


if __name__ == "__main__":
    unittest.main()


