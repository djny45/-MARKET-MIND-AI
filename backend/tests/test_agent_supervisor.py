import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.analytical_agent_tasks import (
    _acquire_supervisor_lease,
    _release_supervisor_lease,
    _renew_supervisor_lease,
    _supervisor_lease_is_valid,
    _write_supervisor_heartbeat,
    agent_supervisor_status,
    agent_task_performance,
    classify_research_task_failure,
    dispatch_queued_research_tasks,
    enqueue_research_task,
    execute_queued_research_task,
    get_research_task,
    recover_interrupted_research_tasks,
    run_supervisor,
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
        self.assertEqual(status["continuous_daemon"], "separate_supervisor_process_required")
        self.assertFalse(status["distributed_queue"])

    def test_supervisor_heartbeat_reports_running_and_stopped_lifecycle(self):
        import threading
        before = agent_supervisor_status()
        self.assertEqual(before["supervisor_health"], "not_started")
        result = run_supervisor(
            threading.Event(), poll_interval_seconds=0.01,
            batch_size=1, max_concurrency=1, max_cycles=1,
        )
        self.assertEqual(result["status"], "cycle_limit_reached")
        after = agent_supervisor_status()
        self.assertEqual(after["supervisor_health"], "stopped")
        self.assertEqual(after["supervisor_heartbeat"]["state"], "stopped")
        self.assertEqual(after["supervisor_heartbeat"]["batch_size"], 1)
        self.assertIsNone(after["supervisor_heartbeat"]["last_error_type"])

    def test_supervisor_heartbeat_staleness_is_detected(self):
        import sqlite3
        import threading
        run_supervisor(
            threading.Event(), poll_interval_seconds=0.01,
            batch_size=1, max_concurrency=1, max_cycles=1,
        )
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_supervisor_heartbeat SET state='running',heartbeat_at=? WHERE singleton_id=1",
                ("2000-01-01T00:00:00+00:00",),
            )
        status = agent_supervisor_status()
        self.assertEqual(status["supervisor_health"], "stale")
        self.assertGreater(status["supervisor_heartbeat"]["heartbeat_age_seconds"], 15)

    def test_fresh_heartbeat_from_dead_process_reports_stale(self):
        """A fresh heartbeat must not mask a SIGKILLed supervisor."""
        import sqlite3
        import threading
        run_supervisor(
            threading.Event(), poll_interval_seconds=0.01,
            batch_size=1, max_concurrency=1, max_cycles=1,
        )
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_supervisor_heartbeat "
                "SET state='running', process_id=?, heartbeat_at=? WHERE singleton_id=1",
                (2147483646, "2100-01-01T00:00:00+00:00"),  # impossible pid, future heartbeat
            )
        status = agent_supervisor_status()
        self.assertEqual(status["supervisor_health"], "stale")
        self.assertFalse(status["supervisor_heartbeat"]["process_alive"])
        self.assertLess(status["supervisor_heartbeat"]["heartbeat_age_seconds"], 1)

    def test_out_of_range_heartbeat_pid_is_not_alive(self):
        import sqlite3
        import threading
        run_supervisor(
            threading.Event(), poll_interval_seconds=0.01,
            batch_size=1, max_concurrency=1, max_cycles=1,
        )
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_supervisor_heartbeat "
                "SET state='running', process_id=?, heartbeat_at=? WHERE singleton_id=1",
                (2147483648, "2100-01-01T00:00:00+00:00"),
            )
        status = agent_supervisor_status()
        self.assertEqual(status["supervisor_health"], "stale")
        self.assertFalse(status["supervisor_heartbeat"]["process_alive"])

    def test_lease_ownership_is_fenced_against_a_second_supervisor(self):
        import sqlite3
        from datetime import datetime, timedelta, timezone
        instance = f"pid-{os.getpid()}"
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        _write_supervisor_heartbeat(
            "running", 1.0, 10, 2, lease_token="token-A", expires_at=expiry
        )
        self.assertTrue(_supervisor_lease_is_valid(instance, "token-A"))
        self.assertFalse(_supervisor_lease_is_valid(instance, "token-B"))
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            db.execute(
                "UPDATE analytical_agent_supervisor_heartbeat "
                "SET instance_id='other', supervisor_lease_token='token-B' WHERE singleton_id=1"
            )
        self.assertFalse(_supervisor_lease_is_valid(instance, "token-A"))
        self.assertFalse(_renew_supervisor_lease(instance, "token-A", 60))

    def test_dispatch_aborts_when_lease_is_lost_between_selection_and_dispatch(self):
        import sqlite3
        import app.analytical_agent_tasks as tasks
        from datetime import datetime, timedelta, timezone
        enqueue_research_task("worker_001", "lease loss sample")
        instance = f"pid-{os.getpid()}"
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        _write_supervisor_heartbeat(
            "running", 1.0, 10, 2, lease_token="token-A", expires_at=expiry
        )
        original = tasks._record_event

        def hijack(db, *args, **kwargs):
            db.execute(
                "UPDATE analytical_agent_supervisor_heartbeat "
                "SET instance_id='other', supervisor_lease_token='token-B' WHERE singleton_id=1"
            )
            return original(db, *args, **kwargs)

        with patch("app.analytical_agent_tasks._record_event", side_effect=hijack):
            result = dispatch_queued_research_tasks(
                limit=5, max_concurrency=1,
                supervisor_instance_id=instance, supervisor_lease_token="token-A",
            )
        self.assertEqual(result["status"], "lease_lost")
        self.assertEqual(result["dispatched"], 0)
        with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
            remaining = db.execute(
                "SELECT COUNT(*) FROM analytical_agent_tasks WHERE status='queued'"
            ).fetchone()[0]
        self.assertEqual(remaining, 1)

    def test_run_supervisor_stops_before_dispatch_when_renewal_fails(self):
        import threading
        with patch("app.analytical_agent_tasks._renew_supervisor_lease", return_value=False), \
             patch("app.analytical_agent_tasks.dispatch_queued_research_tasks") as dispatch:
            result = run_supervisor(
                threading.Event(), poll_interval_seconds=0.01,
                batch_size=1, max_concurrency=1, max_cycles=1,
            )
        self.assertEqual(result["status"], "lease_lost")
        dispatch.assert_not_called()

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

    def test_stale_task_recovers_across_real_process_restart(self):
        # Process one persists a running task and exits, releasing every SQLite
        # connection. Process two simulates supervisor startup recovery.
        child_env = os.environ.copy()
        backend_path = str(__import__("pathlib").Path(__file__).resolve().parents[1])
        child_env["PYTHONPATH"] = os.pathsep.join(
            item for item in (backend_path, child_env.get("PYTHONPATH", "")) if item
        )
        create_code = """
import json, os, sqlite3
from app.analytical_agent_tasks import enqueue_research_task
task = enqueue_research_task("worker_003", "restart recovery integration")
with sqlite3.connect(os.environ["MARKET_MIND_DB"]) as db:
    db.execute(
        "UPDATE analytical_agent_tasks SET status='running', updated_at=? WHERE task_id=?",
        ("2000-01-01T00:00:00+00:00", task["task_id"]),
    )
print(json.dumps(task))
"""
        created = subprocess.check_output(
            [sys.executable, "-c", create_code],
            env=child_env,
            text=True,
        )
        task_id = json.loads(created)["task_id"]

        recover_code = """
import json, sys
from app.analytical_agent_tasks import recover_interrupted_research_tasks, get_research_task
recovery = recover_interrupted_research_tasks(stale_after_seconds=900)
task = get_research_task(sys.argv[1])
print(json.dumps({"recovery": recovery, "status": task["status"]}))
"""
        recovered = subprocess.check_output(
            [sys.executable, "-c", recover_code, task_id],
            env=child_env,
            text=True,
        )
        result = json.loads(recovered)
        self.assertEqual(result["recovery"]["requeued_interrupted_count"], 1)
        self.assertEqual(result["status"], "queued")

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

    def test_lease_acquisition_is_fenced_and_expiry_releases_leadership(self):
        import time
        from datetime import datetime, timedelta, timezone
        instance = f"pid-{os.getpid()}"
        self.assertTrue(_acquire_supervisor_lease(instance, "token-A", 0.3))
        self.assertFalse(_acquire_supervisor_lease("other", "token-B", 0.3))
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=0.3)).isoformat()
        self.assertTrue(_write_supervisor_heartbeat(
            "running", 1.0, 10, 2, lease_token="token-A", expires_at=expiry
        ))
        self.assertTrue(_supervisor_lease_is_valid(instance, "token-A"))
        time.sleep(0.4)
        self.assertFalse(_supervisor_lease_is_valid(instance, "token-A"))
        self.assertFalse(_renew_supervisor_lease(instance, "token-A", 0.3))
        self.assertTrue(_acquire_supervisor_lease("other", "token-B", 0.3))
        self.assertTrue(_release_supervisor_lease("other", "token-B"))
        self.assertFalse(_supervisor_lease_is_valid("other", "token-B"))

    def test_dispatch_renews_lease_during_a_long_running_task(self):
        import threading
        import time
        from datetime import datetime, timedelta, timezone

        enqueue_research_task("worker_001", "long lease sample")
        instance = f"pid-{os.getpid()}"
        lease_seconds = 1.0
        self.assertTrue(_acquire_supervisor_lease(instance, "token-long", lease_seconds))
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        self.assertTrue(_write_supervisor_heartbeat(
            "running", 1.0, 10, 2, lease_token="token-long", expires_at=expiry
        ))
        gate = threading.Event()
        result = {}

        def run():
            with patch("app.analytical_agent_tasks.execute_queued_research_task",
                       side_effect=lambda task_id: gate.wait(10)):
                result["value"] = dispatch_queued_research_tasks(
                    limit=1, max_concurrency=1, supervisor_instance_id=instance,
                    supervisor_lease_token="token-long", lease_seconds=lease_seconds,
                )

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            # Wait several times past the original TTL so renewal has many
            # opportunities even on a heavily loaded CI runner. Polling (rather
            # than one fixed sleep) means scheduler jitter cannot flake the test.
            deadline = time.monotonic() + (lease_seconds * 3)
            while time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(_supervisor_lease_is_valid(instance, "token-long"))
        finally:
            gate.set()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["value"]["status"], "completed")
        self.assertEqual(result["value"]["dispatched"], 1)
        self.assertFalse(result["value"]["lease_lost_during_dispatch"])
        self.assertIsNone(result["value"]["lease_renewal_error_type"])

    def test_dispatch_survives_transient_lease_renewal_error(self):
        """A transient store error must not silently end lease renewal.

        Regression: renewal previously had no exception handling, so one failed
        renewal call killed the only renewal thread and leadership lapsed with no
        visible signal while the task kept running.
        """
        import threading
        import time
        from datetime import datetime, timedelta, timezone

        import app.analytical_agent_tasks as tasks

        enqueue_research_task("worker_001", "renewal error sample")
        instance = f"pid-{os.getpid()}"
        lease_seconds = 1.0
        self.assertTrue(_acquire_supervisor_lease(instance, "token-long", lease_seconds))
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        self.assertTrue(_write_supervisor_heartbeat(
            "running", 1.0, 10, 2, lease_token="token-long", expires_at=expiry
        ))
        gate = threading.Event()
        result = {}
        real_renew = tasks._renew_supervisor_lease
        state = {"raised": False}

        def flaky_renew(instance_id, token, seconds):
            if not state["raised"]:
                state["raised"] = True
                raise RuntimeError("transient store outage")
            return real_renew(instance_id, token, seconds)

        def run():
            with patch("app.analytical_agent_tasks.execute_queued_research_task",
                       side_effect=lambda task_id: gate.wait(10)), \
                 patch("app.analytical_agent_tasks._renew_supervisor_lease",
                       side_effect=flaky_renew):
                result["value"] = dispatch_queued_research_tasks(
                    limit=1, max_concurrency=1, supervisor_instance_id=instance,
                    supervisor_lease_token="token-long", lease_seconds=lease_seconds,
                )

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + (lease_seconds * 3)
            while time.monotonic() < deadline:
                time.sleep(0.1)
            # Renewal kept retrying after the error, so leadership is still held.
            self.assertTrue(state["raised"])
            self.assertTrue(_supervisor_lease_is_valid(instance, "token-long"))
        finally:
            gate.set()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["value"]["status"], "completed")
        self.assertFalse(result["value"]["lease_lost_during_dispatch"])
        self.assertEqual(result["value"]["lease_renewal_error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
