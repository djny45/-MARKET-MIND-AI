"""Tests for persistent daily schedule registration and recovery."""
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/schedule.db"

from app import daily_intelligence as di
from app.analytical_agent_tasks import run_supervisor


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        # A fresh DB per test: a completed daily cycle must never leak into
        # another test's due-cycle assertion.
        self.db_dir = tempfile.mkdtemp()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": self.db_dir + "/schedule.db"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_schedule_is_persistent_across_new_connections(self):
        first = di.schedule_status()
        self.assertTrue(first["enabled"])
        self.assertFalse(first["independent_daemon"])
        # A fresh module-level read simulates a backend restart.
        second = di.schedule_status()
        self.assertEqual(second["enabled"], first["enabled"])
        self.assertEqual(second["next_cycle_id"], first["next_cycle_id"])

    def test_due_cycle_runs_once_and_reports_next(self):
        result = di.due_cycle(publish_zulip=False)
        self.assertIn(result["status"], {"completed", "partial"})
        self.assertTrue(result["scheduler_claimed"])
        state = di.schedule_status()
        self.assertEqual(state["last_cycle_id"], result["cycle_id"])
        self.assertGreater(state["next_cycle_id"], result["cycle_id"])
        repeat = di.due_cycle(publish_zulip=False)
        self.assertEqual(repeat["status"], "skipped")
        self.assertEqual(repeat["reason"], "not_due")

    def test_disable_and_reenable(self):
        di.set_schedule_enabled(False)
        self.assertFalse(di.schedule_status()["enabled"])
        self.assertEqual(di.due_cycle()["status"], "disabled")
        di.set_schedule_enabled(True)
        self.assertTrue(di.schedule_status()["enabled"])

    def test_missed_cycle_recovery_is_recorded(self):
        db = di._schedule_db()
        try:
            db.execute(
                "UPDATE daily_cycle_schedule SET last_cycle_id='daily-2020-01-01' "
                "WHERE singleton_id=1"
            )
            db.commit()
        finally:
            db.close()
        state = di.schedule_status()
        self.assertGreater(state["missed_cycles_recovered"], 0)

    def test_supervisor_registers_daily_cycle_once_in_two_polls(self):
        import threading

        stop = threading.Event()
        with patch("app.daily_intelligence.due_cycle",
                   return_value={"status": "completed", "cycle_id": "daily-2026-11-26"}) as due:
            result = run_supervisor(stop, poll_interval_seconds=0.05, max_cycles=2)
        self.assertEqual(result["cycles"], 2)
        self.assertEqual(due.call_count, 2)  # checked each poll, idempotent inside
        self.assertEqual(len(result["daily_cycle_results"]), 2)

    def test_supervisor_env_can_disable_daily_cycle(self):
        stop = threading.Event()
        with patch.dict(os.environ, {"MARKET_MIND_DAILY_CYCLE_ENABLED": "false"}), \
             patch("app.daily_intelligence.due_cycle") as due:
            result = run_supervisor(stop, poll_interval_seconds=0.05, max_cycles=1)
        due.assert_not_called()
        self.assertEqual(result["daily_cycle_results"], [])


if __name__ == "__main__":
    unittest.main()
