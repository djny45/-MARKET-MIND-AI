import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.analytical_agent_tasks import (
    agent_supervisor_status,
    agent_task_performance,
    classify_research_task_failure,
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
        self.assertEqual(task["execution_attempts"], 1)

    def test_duplicate_dispatch_claims_task_only_once(self):
        queued = enqueue_research_task("worker_004", "duplicate dispatch sample")
        with patch("app.analytical_agent_tasks.synthesize_research", return_value={"status": "completed"}) as synthesize:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(execute_queued_research_task, queued["task_id"])
                           for _ in range(2)]
                for future in futures:
                    future.result()
            self.assertEqual(synthesize.call_count, 1)
        task = get_research_task(queued["task_id"])
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["execution_attempts"], 1)

    def test_queued_task_has_zero_execution_attempts_before_dispatch(self):
        queued = enqueue_research_task("worker_007", "attempt telemetry")
        task = get_research_task(queued["task_id"])
        self.assertEqual(task["execution_attempts"], 0)

    def test_recovery_requeues_interrupted_tasks_without_dispatch(self):
        queued = enqueue_research_task("worker_002", "recover sample")
        import sqlite3
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_tasks SET status='running',updated_at=? WHERE task_id=?",
                ("2000-01-01T00:00:00+00:00", queued["task_id"]),
            )
        result = recover_interrupted_research_tasks()
        self.assertEqual(result["requeued_interrupted_count"], 1)
        self.assertIn(queued["task_id"], result["queued_task_ids"])
        self.assertEqual(get_research_task(queued["task_id"])["status"], "queued")
        self.assertEqual(result["recovery_mode"], "manual_stale_requeue_no_dispatch")
        self.assertEqual(result["stale_after_seconds"], 900)

    def test_recovery_preserves_recent_running_task(self):
        queued = enqueue_research_task("worker_005", "active task sample")
        import sqlite3
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_tasks SET status='running' WHERE task_id=?",
                (queued["task_id"],),
            )
        result = recover_interrupted_research_tasks()
        self.assertEqual(result["requeued_interrupted_count"], 0)
        self.assertEqual(result["still_running_count"], 1)
        self.assertEqual(get_research_task(queued["task_id"])["status"], "running")

    def test_concurrent_recovery_records_only_one_requeue_event(self):
        from app.analytical_agent_tasks import list_task_audit_events
        queued = enqueue_research_task("worker_006", "concurrent recovery")
        import sqlite3
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_tasks SET status='running',updated_at=? WHERE task_id=?",
                ("2000-01-01T00:00:00+00:00", queued["task_id"]),
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: recover_interrupted_research_tasks(), range(2)))
        self.assertEqual(sum(item["requeued_interrupted_count"] for item in results), 1)
        events = list_task_audit_events(queued["task_id"])["events"]
        requeued = [event for event in events if event["event_type"] == "task_requeued"]
        self.assertEqual(len(requeued), 1)
        self.assertEqual(get_research_task(queued["task_id"])["status"], "queued")

    def test_recovery_grace_period_must_be_positive_integer(self):
        with self.assertRaises(ValueError):
            recover_interrupted_research_tasks(stale_after_seconds=0)
        with self.assertRaises(ValueError):
            recover_interrupted_research_tasks(stale_after_seconds=True)

    def test_completed_research_persists_metrics_only_learning_candidate(self):
        from app.worker_memory import read_memory
        queued = enqueue_research_task(
            "worker_009",
            "traceability evaluation",
            data={
                "draft": "Claim summary with source references and limitations.",
                "claims": [{"text": "Example claim", "source_refs": ["source-a"]}],
                "source_registry": [{"source_id": "source-a", "title": "Example source"}],
            },
        )
        with patch("app.analytical_agent_tasks.synthesize_research", return_value={
            "status": "completed", "summary": "Example claim summary"
        }):
            execute_queued_research_task(queued["task_id"])
        task = get_research_task(queued["task_id"])
        candidate = task["result"]["research_learning_candidate"]
        self.assertEqual(candidate["status"], "persisted_review_candidate")
        memories = read_memory("worker_009", memory_type="validation_result")
        self.assertEqual(memories["count"], 1)
        note = memories["memory"][0]["content"]
        self.assertEqual(note["record_type"], "research_quality_learning_candidate")
        self.assertTrue(note["review_required"])
        self.assertEqual(note["learning_boundary"], "metrics_only_no_claim_truth_or_strategy_learning")

    def test_task_performance_includes_attempt_and_failure_class_metrics(self):
        queued = enqueue_research_task("worker_008", "metrics failure")
        with patch("app.analytical_agent_tasks.synthesize_research", side_effect=TimeoutError("request timed out")):
            execute_queued_research_task(queued["task_id"])
        metrics = agent_task_performance("worker_008")
        worker = metrics["agents"]["worker_008"]
        self.assertEqual(worker["execution_attempts_total"], 1)
        self.assertEqual(worker["average_execution_attempts_per_task"], 1.0)
        self.assertEqual(worker["failure_class_counts"]["transient_candidate"], 1)

    def test_failure_classifier_marks_network_timeout_as_transient_candidate(self):
        result = classify_research_task_failure(TimeoutError("provider request timed out"))
        self.assertEqual(result["failure_class"], "transient_candidate")
        self.assertEqual(result["retry_recommendation"], "operator_review")
        self.assertFalse(result["automatic_retry"])

    def test_failure_classifier_does_not_assume_unknown_errors_are_retryable(self):
        result = classify_research_task_failure(ValueError("invalid task payload"))
        self.assertEqual(result["failure_class"], "non_transient_candidate")
        self.assertEqual(result["retry_recommendation"], "inspect_before_retry")
        self.assertFalse(result["automatic_retry"])

    def test_dispatch_bounds_are_validated(self):
        with self.assertRaises(ValueError):
            dispatch_queued_research_tasks(limit=0)
        with self.assertRaises(ValueError):
            dispatch_queued_research_tasks(max_concurrency=17)


if __name__ == "__main__":
    unittest.main()
