"""Isolated two-process supervisor lease-race worker (test fixture only).

Usage: python supervisor_race_worker.py <db> <ready_file> <start_file> <output_file>
Each process signals readiness, waits for the shared start file, then runs one
supervisor cycle against the shared SQLite database.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path


def main() -> None:
    database, ready_file, start_file, output_file = sys.argv[1:5]
    os.environ["MARKET_MIND_DB"] = database
    os.environ["INTELLIGENCE_CORE_ENABLED"] = "false"
    Path(ready_file).write_text("ready", encoding="utf-8")
    deadline = time.time() + 20
    while not Path(start_file).exists():
        if time.time() > deadline:
            raise SystemExit("start file timeout")
        time.sleep(0.005)

    from app.analytical_agent_tasks import run_supervisor

    result = run_supervisor(
        threading.Event(), poll_interval_seconds=0.01,
        batch_size=1, max_concurrency=1, max_cycles=1,
    )
    Path(output_file).write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
