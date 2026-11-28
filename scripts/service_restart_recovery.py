#!/usr/bin/env python3
"""Post-restart recovery hook for the research stack.

Combines three explicit, idempotent checks:
  1. clear stale DR lock files left by interrupted backup/restore processes,
  2. verify SQLite integrity of the active research database,
  3. invoke the application's own stale-task requeue (no dispatch) so that
     interrupted research tasks survive a service restart.

It never starts live trading, wallet keys, signing or order routing.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dr_common import (
    REPO_ROOT, DrError, DrLock, atomic_write_json, env_int, iso_now, positive_int,
    readonly_uri, redact_secrets, send_alert, utcstamp,
)


class RecoveryConfig:
    def __init__(self, args):
        state_dir = args.state_dir or os.getenv("MARKET_MIND_DR_STATE_DIR", "./data/backups/.state")
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.db = Path(
            args.db or os.getenv("MARKET_MIND_DB", "./data/market_mind.db")
        ).expanduser().resolve()
        if args.stale_after_seconds is not None:
            self.stale_after = positive_int(
                args.stale_after_seconds, "stale_after_seconds"
            )
        else:
            self.stale_after = env_int("MARKET_MIND_RECOVERY_STALE_SECONDS", 900)
        self.skip_tasks = args.skip_task_recovery
        self.timeout = env_int("MARKET_MIND_DR_TIMEOUT_SECONDS", 300)


def database_integrity(db: Path) -> dict:
    if not db.is_file():
        return {"status": "missing", "database": str(db)}
    try:
        with sqlite3.connect(readonly_uri(db), uri=True) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            tables = {
                name for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            heartbeat = None
            if "analytical_agent_supervisor_heartbeat" in tables:
                record = connection.execute(
                    "SELECT state, heartbeat_at FROM "
                    "analytical_agent_supervisor_heartbeat WHERE singleton_id=1"
                ).fetchone()
                if record:
                    age = None
                    try:
                        stamp = datetime.fromisoformat(record[1].replace("Z", "+00:00"))
                        age = (datetime.now(timezone.utc) - stamp).total_seconds()
                    except (ValueError, TypeError):
                        pass
                    heartbeat = {"state": record[0], "age_seconds": age}
    except sqlite3.Error as exc:
        return {"status": "error", "error_type": type(exc).__name__}
    return {
        "status": "ok" if row and row[0] == "ok" else "failed",
        "integrity": row[0] if row else "no_result",
        "table_count": len(tables),
        "supervisor_heartbeat": heartbeat,
    }


def requeue_interrupted_tasks(config: RecoveryConfig) -> dict:
    """Call the app's explicit stale-task requeue; never dispatches directly."""
    code = (
        "import json, sys; "
        "from app.analytical_agent_tasks import recover_interrupted_research_tasks; "
        "print(json.dumps(recover_interrupted_research_tasks(int(sys.argv[1]))))"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPO_ROOT / "backend"), env.get("PYTHONPATH", "")) if part
    )
    env["MARKET_MIND_DB"] = str(config.db)
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code, str(config.stale_after)],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
            timeout=config.timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DrError("task_recovery_invocation_failed:" + type(exc).__name__) from exc
    for line in reversed(completed.stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                payload = json.loads(line)
            except ValueError:
                continue
            if completed.returncode == 0:
                return {"status": "ok", "recovery": payload}
            break
    raise DrError(
        "task_recovery_failed:" + redact_secrets(
            completed.stderr.strip()[-300:] or str(completed.returncode)
        )
    )


RECOVERY_JOURNAL = "recovery-journal.json"


def _write_journal(config: RecoveryConfig, phase: str, status: str, **extra) -> None:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(config.state_dir / RECOVERY_JOURNAL, {
        "status": status, "phase": phase, "updated_at": iso_now(), **extra,
    })


def run_recovery(config: RecoveryConfig) -> dict:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    with DrLock(config.state_dir, "recovery"):
        _write_journal(config, "started", "in_progress")
        try:
            stale_locks = DrLock(config.state_dir, "backup").stale_count()
            _write_journal(config, "locks_cleared", "in_progress",
                           stale_dr_locks_removed=stale_locks)
            integrity = database_integrity(config.db)
            if integrity["status"] != "ok":
                raise DrError("database_integrity_failed:" + str(integrity.get("integrity")))
            _write_journal(config, "integrity", "in_progress")
            tasks = {"status": "skipped"}
            if not config.skip_tasks:
                tasks = requeue_interrupted_tasks(config)
            _write_journal(config, "requeue", "in_progress")
            report = {
                "status": "recovered",
                "checked_at": iso_now(),
                "database": str(config.db),
                "stale_dr_locks_removed": stale_locks,
                "database_integrity": integrity,
                "interrupted_task_recovery": tasks,
                "stale_after_seconds": config.stale_after,
                "mode": "explicit_requeue_no_dispatch",
            }
            atomic_write_json(
                config.state_dir / f"restart-recovery-{utcstamp()}.json", report
            )
            _write_journal(config, "reported", "completed")
            return report
        except DrError as exc:
            failed = {
                "status": "failed", "error_type": type(exc).__name__,
                "error": str(exc), "failed_at": iso_now(),
            }
            atomic_write_json(
                config.state_dir / f"restart-recovery-{utcstamp()}.json", failed
            )
            _write_journal(config, "failed", "failed")
            raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--db")
    parser.add_argument("--state-dir")
    parser.add_argument("--stale-after-seconds", type=int)
    parser.add_argument("--skip-task-recovery", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = RecoveryConfig(args)
        result = run_recovery(config)
        exit_code = 0
    except (DrError, OSError, ValueError, sqlite3.Error) as exc:
        error_type = type(exc).__name__
        result = {"status": "failed", "error_type": error_type, "error": str(exc)}
        result["alert"] = send_alert(
            "restart_recovery_failed", "failed",
            {"error_type": error_type, "reason": str(exc)},
        )
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
