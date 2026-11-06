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

    def test_dispatch_counts_only_tasks_it_actually_claimed(self):
        from app.analytical_agent_tasks import enqueue_research_task, dispatch_queued_research_tasks
        queued = enqueue_research_task("worker_018", "dispatch no-op count")
        with patch("app.analytical_agent_tasks.execute_queued_research_task", return_value=False):
            result = dispatch_queued_research_tasks(limit=1, max_concurrency=1)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["dispatched"], 0)
        self.assertEqual(get_research_task(queued["task_id"])["status"], "queued")

    def test_dispatch_reports_worker_exceptions_without_stopping_siblings(self):
        from app.analytical_agent_tasks import enqueue_research_task, dispatch_queued_research_tasks
        first = enqueue_research_task("worker_019", "dispatch exception case")
        second = enqueue_research_task("worker_020", "dispatch healthy sibling")
        from app.analytical_agent_tasks import execute_queued_research_task as real_execute
        def fake_execute(task_id):
            if task_id == first["task_id"]:
                raise RuntimeError("internal detail should not be exposed")
            return real_execute(task_id)
        with patch("app.analytical_agent_tasks.execute_queued_research_task", side_effect=fake_execute):
            result = dispatch_queued_research_tasks(limit=2, max_concurrency=1)
        self.assertEqual(result["selected"], 2)
        self.assertEqual(result["dispatched"], 1)
        self.assertEqual(result["dispatch_error_count"], 1)
        self.assertEqual(result["dispatch_errors"], [{"task_id": first["task_id"], "error_type": "RuntimeError"}])
        self.assertEqual(get_research_task(second["task_id"])["status"], "completed")

    def test_agent_task_performance_reports_outcome_rates(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, agent_task_performance,
        )
        completed = enqueue_research_task("worker_021", "metrics success")
        execute_queued_research_task(completed["task_id"])
        failed = enqueue_research_task("worker_021", "metrics failure")
        with patch("app.analytical_agent_tasks.synthesize_research", side_effect=RuntimeError("offline test")):
            execute_queued_research_task(failed["task_id"])
        queued = enqueue_research_task("worker_022", "metrics queued")
        metrics = agent_task_performance("worker_021")
        worker = metrics["agents"]["worker_021"]
        self.assertEqual(worker["task_count"], 2)
        self.assertEqual(worker["completed"], 1)
        self.assertEqual(worker["failed"], 1)
        self.assertEqual(worker["completion_rate"], 0.5)
        self.assertEqual(worker["failure_rate"], 0.5)
        self.assertEqual(metrics["recent_agents"]["worker_021"]["finished_count"], 2)
        all_metrics = agent_task_performance()
        self.assertEqual(all_metrics["agents"]["worker_022"]["queued"], 1)
        self.assertEqual(all_metrics["task_count"], 3)
        with self.assertRaises(ValueError):
            agent_task_performance("worker_021", limit=0)

    def test_agent_research_quality_performance_aggregates_saved_evaluations(self):
        from app.analytical_agent_tasks import (
            enqueue_research_task, execute_queued_research_task, agent_research_quality_performance,
        )
        for idx, draft in enumerate(("Draft with limitation.", "Second draft with uncertainty.")):
            queued = enqueue_research_task(
                "worker_023", "quality aggregation " + str(idx),
                {"draft": draft,
                 "claims": [{"text": "Claim", "source_refs": ["s1"]},
                            {"text": "Another claim", "source_refs": []}],
                 "source_registry": [{"source_id": "s1"}]},
            )
            execute_queued_research_task(queued["task_id"])
        result = agent_research_quality_performance("worker_023")
        worker = result["agents"]["worker_023"]
        self.assertEqual(worker["evaluation_count"], 2)
        self.assertEqual(worker["claim_reference_coverage_mean"], 0.5)
        self.assertEqual(worker["known_source_reference_coverage_mean"], 0.5)
        self.assertEqual(result["evaluations_examined"], 2)
        with self.assertRaises(ValueError):
            agent_research_quality_performance("worker_023", limit=0)

    def test_supervisor_recommendations_are_advisory_and_evidence_gated(self):
        from app.analytical_agent_tasks import agent_supervisor_recommendations
        with patch("app.analytical_agent_tasks.agent_task_performance", return_value={
            "agents": {
                "worker_fail": {"finished_count": 6, "failure_rate": 0.5},
                "worker_good": {"finished_count": 8, "failure_rate": 0.0},
            }
        }), patch("app.analytical_agent_tasks.agent_research_quality_performance", return_value={
            "agents": {
                "worker_fail": {"evaluation_count": 0},
                "worker_good": {"evaluation_count": 4, "known_source_reference_coverage_mean": 0.95},
                "worker_low_refs": {"evaluation_count": 4, "known_source_reference_coverage_mean": 0.4},
            }
        }):
            result = agent_supervisor_recommendations()
        reasons = {(item["agent_id"], item["reason_code"]) for item in result["recommendations"]}
        self.assertIn(("worker_fail", "repeated_task_failures"), reasons)
        self.assertIn(("worker_good", "consistent_structural_traceability"), reasons)
        self.assertIn(("worker_low_refs", "low_source_reference_coverage"), reasons)
        self.assertEqual(result["decision_mode"], "advisory_only")
        self.assertTrue(any("No autonomous" in item for item in result["limitations"]))

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

    def test_duplicate_dispatch_only_claims_once(self):
        from app.analytical_agent_tasks import enqueue_research_task, execute_queued_research_task
        queued = enqueue_research_task("worker_006", "single claim")
        execute_queued_research_task(queued["task_id"])
        first = get_research_task(queued["task_id"])
        execute_queued_research_task(queued["task_id"])
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

if __name__ == "__main__":
    unittest.main()


