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

    def test_task_database_connections_are_closed_after_use(self):
        import sqlite3
        from app.analytical_agent_tasks import _connect

        original_connect = sqlite3.connect
        tracked = []

        class TrackingConnection(sqlite3.Connection):
            was_closed = False

            def close(self):
                self.was_closed = True
                super().close()

        def tracked_connect(*args, **kwargs):
            kwargs["factory"] = TrackingConnection
            connection = original_connect(*args, **kwargs)
            tracked.append(connection)
            return connection

        with patch("app.analytical_agent_tasks.sqlite3.connect", side_effect=tracked_connect):
            with _connect() as db:
                db.execute("SELECT 1")

        self.assertEqual(len(tracked), 1)
        self.assertTrue(tracked[0].was_closed)

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

    def test_queued_task_includes_optional_traceability_evaluation(self):
        from app.analytical_agent_tasks import enqueue_research_task, execute_queued_research_task
        queued = enqueue_research_task(
            "worker_014",
            "Evaluate supplied claims",
            {
                "draft": "Draft includes limitations and unknowns.",
                "claims": [
                    {"text": "Claim with a source", "source_refs": ["source-1"]},
                    {"text": "Claim without source", "source_refs": []},
                ],
                "source_registry": [{"source_id": "source-1"}],
            },
        )
        execute_queued_research_task(queued["task_id"])
        result = get_research_task(queued["task_id"])["result"]
        evaluation = result["research_quality_evaluation"]
        self.assertEqual(result["research_quality_evaluation_status"], "evaluated")
        self.assertEqual(evaluation["evaluation_type"], "deterministic_research_traceability_check")
        self.assertEqual(evaluation["metrics"]["claim_reference_coverage"], 0.5)
        self.assertEqual(evaluation["metrics"]["known_source_reference_coverage"], 0.5)

    def test_task_audit_events_record_queue_claim_and_completion(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, list_task_audit_events,
        )
        queued = enqueue_research_task("worker_007", "audit lifecycle")
        execute_queued_research_task(queued["task_id"])
        audit = list_task_audit_events(queued["task_id"])
        self.assertEqual(
            [event["event_type"] for event in audit["events"]],
            ["task_queued", "task_claimed", "task_completed"],
        )
        self.assertEqual(audit["events"][0]["to_status"], "queued")
        self.assertEqual(audit["events"][1]["from_status"], "queued")
        self.assertEqual(audit["events"][2]["to_status"], "completed")

    def test_synchronous_submission_records_audit_lifecycle(self):
        from app.analytical_agent_tasks import list_task_audit_events
        result = submit_research_task("worker_009", "sync audit")
        events = list_task_audit_events(result["task_id"])["events"]
        self.assertEqual(
            [event["event_type"] for event in events],
            ["task_submitted", "task_completed"],
        )
        self.assertEqual(events[0]["to_status"], "running")
        self.assertEqual(events[-1]["to_status"], result["status"])

    def test_manual_dispatch_records_selection_and_completion(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, dispatch_queued_research_tasks, list_task_audit_events,
        )
        queued = enqueue_research_task("worker_010", "dispatch audit")
        result = dispatch_queued_research_tasks(limit=1, max_concurrency=1)
        self.assertEqual(result["selected"], 1)
        events = list_task_audit_events(queued["task_id"])["events"]
        event_types = [event["event_type"] for event in events]
        self.assertIn("task_dispatch_selected", event_types)
        self.assertIn("task_claimed", event_types)
        self.assertIn("task_dispatch_finished", event_types)

    def test_network_activity_snapshot_includes_recent_audit_events(self):
        from app.analytical_agent_tasks import list_recent_task_activity
        result = submit_research_task("worker_011", "activity audit snapshot")
        snapshot = list_recent_task_activity(limit=10)
        matching = [event for event in snapshot["recent_audit_events"]
                    if event["task_id"] == result["task_id"]]
        self.assertEqual(
            [event["event_type"] for event in matching],
            ["task_submitted", "task_completed"],
        )
        self.assertEqual(snapshot["audit_event_count"], len(snapshot["recent_audit_events"]))

    def test_task_audit_events_are_bounded_and_unknown_task_is_empty(self):
        from app.analytical_agent_tasks import enqueue_research_task, list_task_audit_events
        queued = enqueue_research_task("worker_008", "audit bounds")
        self.assertEqual(list_task_audit_events(queued["task_id"], limit=1)["count"], 1)
        self.assertEqual(list_task_audit_events("unknown-task")["events"], [])
        with self.assertRaises(ValueError):
            list_task_audit_events(queued["task_id"], limit=0)

    def test_task_audit_events_can_filter_by_event_type(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, list_task_audit_events,
        )
        queued = enqueue_research_task("worker_012", "audit event filter")
        execute_queued_research_task(queued["task_id"])
        filtered = list_task_audit_events(queued["task_id"], event_type="task_completed")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["events"][0]["event_type"], "task_completed")
        self.assertEqual(list_task_audit_events(queued["task_id"], event_type="unknown_event")["count"], 0)
        with self.assertRaises(ValueError):
            list_task_audit_events(queued["task_id"], event_type="")

    def test_task_audit_cursor_paginates_without_repeating_events(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, list_task_audit_events,
        )
        queued = enqueue_research_task("worker_013", "audit cursor paging")
        execute_queued_research_task(queued["task_id"])
        first = list_task_audit_events(queued["task_id"], limit=2)
        self.assertEqual(first["count"], 2)
        cursor = first["next_before_event_id"]
        self.assertIsNotNone(cursor)
        second = list_task_audit_events(queued["task_id"], limit=2, before_event_id=cursor)
        self.assertTrue(second["count"] >= 1)
        first_ids = {event["event_id"] for event in first["events"]}
        second_ids = {event["event_id"] for event in second["events"]}
        self.assertTrue(first_ids.isdisjoint(second_ids))
        self.assertEqual(first["events"][-1]["event_id"] > second["events"][-1]["event_id"], True)
        with self.assertRaises(ValueError):
            list_task_audit_events(queued["task_id"], before_event_id=0)

    def test_queue_task_rejects_invalid_worker(self):
        from app.analytical_agent_tasks import enqueue_research_task
        with self.assertRaises(ValueError):
            enqueue_research_task("worker_9999", "Invalid worker")



    def test_recovery_requeues_stale_running_tasks_and_preserves_queued(self):
        from app.analytical_agent_tasks import enqueue_research_task, recover_interrupted_research_tasks
        from datetime import datetime, timedelta, timezone
        queued = enqueue_research_task("worker_005", "recover me")
        import sqlite3
        stale_timestamp = (datetime.now(timezone.utc) - timedelta(seconds=1200)).isoformat()
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_tasks SET status='running',updated_at=? WHERE task_id=?",
                (stale_timestamp, queued["task_id"]),
            )
        recovery = recover_interrupted_research_tasks()
        self.assertEqual(recovery["requeued_interrupted_count"], 1)
        self.assertEqual(recovery["recovery_mode"], "manual_stale_requeue_no_dispatch")
        self.assertEqual(get_research_task(queued["task_id"])["status"], "queued")

    def test_concurrent_dispatchers_execute_a_queued_task_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Lock
        from app.analytical_agent_tasks import enqueue_research_task, dispatch_queued_research_tasks

        queued = enqueue_research_task("worker_021", "concurrent dispatcher claim")
        call_lock = Lock()
        calls = 0

        def counted_synthesis(payload):
            nonlocal calls
            with call_lock:
                calls += 1
            return {"status": "not_configured"}

        with patch("app.analytical_agent_tasks.synthesize_research", side_effect=counted_synthesis):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(
                    lambda _: dispatch_queued_research_tasks(limit=1, max_concurrency=1),
                    range(2),
                ))

        self.assertEqual(sum(result["dispatched"] for result in results), 1)
        self.assertEqual(calls, 1)
        self.assertEqual(get_research_task(queued["task_id"])["status"], "completed")

    def test_duplicate_dispatch_only_claims_once(self):
        from app.analytical_agent_tasks import enqueue_research_task, execute_queued_research_task
        queued = enqueue_research_task("worker_006", "single claim")
        self.assertTrue(execute_queued_research_task(queued["task_id"]))
        first = get_research_task(queued["task_id"])
        self.assertFalse(execute_queued_research_task(queued["task_id"]))
        second = get_research_task(queued["task_id"])
        self.assertEqual(first["status"], second["status"])
        self.assertEqual(first["updated_at"], second["updated_at"])


    def test_traceability_evaluation_is_persisted_and_retrievable(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, get_task_quality_evaluation,
        )
        queued = enqueue_research_task(
            "worker_016",
            "Persist traceability report",
            {
                "draft": "An assumption is stated.",
                "claims": [{"text": "Claim", "source_refs": ["src"]}],
                "source_registry": [{"source_id": "src"}],
            },
        )
        execute_queued_research_task(queued["task_id"])
        saved = get_task_quality_evaluation(queued["task_id"])
        self.assertEqual(saved["status"], "persisted")
        self.assertEqual(saved["task_id"], queued["task_id"])
        self.assertEqual(saved["evaluation"]["metrics"]["known_source_reference_coverage"], 1.0)
        self.assertIsNone(get_task_quality_evaluation("unknown-task"))

    def test_task_without_quality_evaluation_returns_not_evaluated(self):
        from app.analytical_agent_tasks import enqueue_research_task, get_task_quality_evaluation
        queued = enqueue_research_task("worker_017", "No evaluation supplied")
        result = get_task_quality_evaluation(queued["task_id"])
        self.assertEqual(result["status"], "not_evaluated")
        self.assertIsNone(result["evaluation"])

    def test_invalid_optional_traceability_input_does_not_fail_task(self):
        from app.analytical_agent_tasks import enqueue_research_task, execute_queued_research_task
        queued = enqueue_research_task(
            "worker_015",
            "Keep research task resilient to invalid optional quality metadata",
            {
                "draft": "A draft with an assumption.",
                "claims": [{"text": "Claim", "source_refs": ["ref-1"]}],
                "source_registry": ["malformed-source-entry"],
            },
        )
        execute_queued_research_task(queued["task_id"])
        saved = get_research_task(queued["task_id"])
        self.assertEqual(saved["status"], "completed")
        result = saved["result"]
        self.assertEqual(result["research_quality_evaluation_status"], "invalid_evaluation_input")
        self.assertEqual(result["research_quality_evaluation"]["status"], "invalid_input")
        self.assertIn("entries must be objects", result["research_quality_evaluation"]["error"])
        self.assertEqual(result["shared_core_result"]["status"], "not_configured")



    def test_corrupt_queued_input_marks_claimed_task_failed(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, list_task_audit_events,
        )
        import sqlite3
        queued = enqueue_research_task("worker_019", "corrupt persisted input")
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_tasks SET input_json=? WHERE task_id=?",
                ("{not valid json", queued["task_id"]),
            )

        execute_queued_research_task(queued["task_id"])

        saved = get_research_task(queued["task_id"])
        self.assertEqual(saved["status"], "failed")
        self.assertIsNone(saved["input"])
        self.assertTrue(saved["input_decode_error"])
        self.assertEqual(saved["result"]["error"], "Research task failed safely.")
        self.assertEqual(saved["result"]["error_type"], "JSONDecodeError")
        events = list_task_audit_events(queued["task_id"])["events"]
        self.assertEqual(events[-1]["event_type"], "task_failed")
        self.assertEqual(events[-1]["to_status"], "failed")


    def test_sync_memory_retrieval_failure_marks_task_failed(self):
        from app.analytical_agent_tasks import list_task_audit_events
        with patch("app.analytical_agent_tasks.recall_memory", side_effect=RuntimeError("memory unavailable")):
            result = submit_research_task("worker_020", "sync memory failure")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["result"]["error"], "Research task failed safely.")
        self.assertEqual(result["result"]["error_type"], "RuntimeError")
        saved = get_research_task(result["task_id"])
        self.assertEqual(saved["status"], "failed")
        events = list_task_audit_events(result["task_id"])["events"]
        self.assertEqual(events[-1]["event_type"], "task_failed")
        self.assertEqual(events[-1]["to_status"], "failed")

    def test_memory_retrieval_failure_marks_claimed_task_failed(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, list_task_audit_events,
        )
        queued = enqueue_research_task("worker_018", "memory retrieval failure test")
        with patch("app.analytical_agent_tasks.recall_memory", side_effect=RuntimeError("memory unavailable")):
            execute_queued_research_task(queued["task_id"])
        saved = get_research_task(queued["task_id"])
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["result"]["error"], "Research task failed safely.")
        self.assertEqual(saved["result"]["error_type"], "RuntimeError")
        events = list_task_audit_events(queued["task_id"])["events"]
        self.assertEqual(events[-1]["event_type"], "task_failed")
        self.assertEqual(events[-1]["to_status"], "failed")

    def test_dispatch_reports_failed_task_outcomes(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, dispatch_queued_research_tasks,
        )
        queued = enqueue_research_task("worker_019", "dispatch failure outcome")
        with patch("app.analytical_agent_tasks.synthesize_research",
                   side_effect=RuntimeError("research provider failed")):
            result = dispatch_queued_research_tasks(limit=1, max_concurrency=1)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["dispatched"], 1)
        self.assertEqual(result["task_status_counts"]["failed"], 1)
        self.assertEqual(result["failed_task_count"], 1)
        self.assertEqual(get_research_task(queued["task_id"])["status"], "failed")


if __name__ == "__main__":
    unittest.main()


