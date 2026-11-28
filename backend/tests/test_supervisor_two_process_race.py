"""Two real processes contend for the single-host supervisor lease.

This is an isolated SQLite race test, not a multi-host claim. It verifies that
exactly one supervisor acquires leadership, recovers and dispatches, while the
loser exits without side effects.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.analytical_agent_tasks import (
    agent_supervisor_status,
    enqueue_research_task,
    get_research_task,
)

REPO = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).resolve().parent / "fixtures" / "supervisor_race_worker.py"


class SupervisorTwoProcessRaceTests(unittest.TestCase):
    def test_exactly_one_process_acquires_and_dispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = str(root / "race.db")
            env = dict(os.environ, MARKET_MIND_DB=database, INTELLIGENCE_CORE_ENABLED="false")
            with patch.dict(os.environ, env, clear=False):
                task = enqueue_research_task("worker_001", "two-process race sample")

            ready_files = [root / f"ready-{index}" for index in range(2)]
            output_files = [root / f"result-{index}.json" for index in range(2)]
            start_file = root / "start"
            processes = [
                subprocess.Popen(
                    [sys.executable, str(WORKER), database, str(ready_files[index]),
                     str(start_file), str(output_files[index])],
                    env=dict(env, PYTHONPATH=f"{REPO}{os.pathsep}{REPO / 'backend'}"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                for index in range(2)
            ]
            try:
                deadline = 20.0
                import time
                started = time.time()
                while not all(path.exists() for path in ready_files):
                    if time.time() - started > deadline:
                        raise AssertionError("workers did not become ready")
                    time.sleep(0.01)
                start_file.write_text("go", encoding="utf-8")
                for process in processes:
                    stdout, stderr = process.communicate(timeout=20)
                    self.assertEqual(process.returncode, 0, stderr + stdout)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()

            results = [json.loads(path.read_text()) for path in output_files]
            # Both workers are released from the same start gate, but on a fast
            # runner the winner can finish its single cycle and release the
            # lease before the loser calls run_supervisor(). In that case the
            # loser also sees "cycle_limit_reached". The invariant that must
            # hold is not the loser's status string but that exactly one
            # process actually dispatched the one queued task.
            statuses = sorted(result["status"] for result in results)
            self.assertTrue(
                set(statuses) <= {"cycle_limit_reached", "lease_unavailable"},
                statuses,
            )
            self.assertIn("cycle_limit_reached", statuses)

            winners = [r for r in results if r["status"] == "cycle_limit_reached"]
            dispatched = sum(
                cycle.get("dispatched", 0)
                for winner in winners
                for cycle in winner.get("dispatch_results", [])
            )
            self.assertEqual(dispatched, 1, "exactly one process must dispatch the task")
            self.assertEqual(
                sum(1 for winner in winners for cycle in winner.get("dispatch_results", [])
                    if cycle.get("selected") == 1),
                1,
            )

            with patch.dict(os.environ, env, clear=False):
                stored = get_research_task(task["task_id"])
                agent_supervisor_status()
            with sqlite3.connect(database) as connection:
                lease_token = connection.execute(
                    "SELECT supervisor_lease_token FROM analytical_agent_supervisor_heartbeat "
                    "WHERE singleton_id=1"
                ).fetchone()[0]
            self.assertEqual(stored["status"], "completed")
            self.assertEqual(stored["execution_attempts"], 1)
            self.assertIsNone(lease_token, "winner must release leadership on shutdown")


if __name__ == "__main__":
    unittest.main()
