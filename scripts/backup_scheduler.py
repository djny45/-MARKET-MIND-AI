#!/usr/bin/env python3
"""Scheduling hooks for the verified research-database backup job.

This script does NOT install anything into the host. It either runs one backup
now (``run``, suitable for cron/systemd) or prints a cron line / systemd timer
that an operator can install deliberately. Configuration stays in environment
variables so no credentials are embedded in unit files or crontabs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

from dr_common import REPO_ROOT, DrError, env_int, positive_int, run_repo_script

ORCHESTRATOR = Path(__file__).with_name("backup_orchestrator.py")


def run_once() -> dict:
    result = run_repo_script(ORCHESTRATOR, ["run"])
    return {
        "status": "completed" if result["returncode"] == 0 else "failed",
        "returncode": result["returncode"],
        "result": result["payload"],
        "stderr": result["stderr"][-1000:],
    }


def _valid_cron_field(value: str, low: int, high: int) -> bool:
    if value == "*":
        return True
    step_match = re.fullmatch(r"\*/(\d+)", value)
    if step_match:
        return int(step_match.group(1)) >= 1
    for part in value.split(","):
        range_step = re.fullmatch(r"(\d+)-(\d+)(?:/(\d+))?", part)
        if range_step:
            start, end = int(range_step.group(1)), int(range_step.group(2))
            step = int(range_step.group(3)) if range_step.group(3) else 1
            if not (low <= start <= end <= high and step >= 1):
                return False
            continue
        if not part.isdigit() or not (low <= int(part) <= high):
            return False
    return True


def cron_line(schedule: str, log_path: str | None) -> dict:
    fields = schedule.split()
    if len(fields) != 5:
        raise DrError("cron_schedule_must_have_5_fields")
    bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    for index, (value, (low, high)) in enumerate(zip(fields, bounds), start=1):
        if not _valid_cron_field(value, low, high):
            raise DrError(f"cron_field_{index}_invalid")
    command = " ".join(shlex.quote(part) for part in (
        sys.executable, str(Path(__file__).resolve()), "run",
    ))
    if log_path:
        command += " >> " + shlex.quote(log_path) + " 2>&1"
    return {
        "status": "ok",
        "schedule": schedule,
        "line": f"{schedule} cd {shlex.quote(str(REPO_ROOT))} && {command}",
        "note": "Install with crontab -e; keep secrets in the service environment.",
    }


def systemd_units(interval_hours: int, on_calendar: str | None) -> dict:
    hours = positive_int(interval_hours, "interval_hours")
    if on_calendar is not None:
        expression = on_calendar.strip()
        if not expression or len(expression) > 120 or "\n" in expression:
            raise DrError("on_calendar_invalid")
        on_calendar = expression
    script = Path(__file__).resolve()
    service = "\n".join([
        "[Unit]",
        "Description=MARKET-MIND verified research database backup",
        "After=network-online.target",
        "",
        "[Service]",
        "Type=oneshot",
        f"WorkingDirectory={REPO_ROOT}",
        f"ExecStart={shlex.quote(sys.executable)} {shlex.quote(str(script))} run",
        "# Supply MARKET_MIND_DB / MARKET_MIND_BACKUP_DIR / retention / webhook",
        "# via EnvironmentFile= with 0600 permissions (never inline secrets).",
        "",
    ])
    timer = "\n".join([
        "[Unit]",
        "Description=Daily MARKET-MIND research database backup",
        "",
        "[Timer]",
        "OnUnitActiveSec={0}h".format(hours) if not on_calendar else f"OnCalendar={on_calendar}",
        "Persistent=true",
        "Unit=market-mind-backup.service",
        "",
        "[Install]",
        "WantedBy=timers.target",
        "",
    ])
    return {"status": "ok", "service": service, "timer": timer,
            "interval_hours": None if on_calendar else hours}


def effective_config() -> dict:
    return {
        "status": "ok",
        "source": os.getenv("MARKET_MIND_DB", "./data/market_mind.db"),
        "backup_dir": os.getenv("MARKET_MIND_BACKUP_DIR", "./data/backups"),
        "retention_days": os.getenv("MARKET_MIND_BACKUP_RETENTION_DAYS", "30"),
        "retention_count": os.getenv("MARKET_MIND_BACKUP_KEEP", ""),
        "upload_hook_configured": bool(os.getenv("MARKET_MIND_BACKUP_UPLOAD_CMD", "").strip()),
        "incident_webhook_configured": bool(
            os.getenv("MARKET_MIND_INCIDENT_WEBHOOK_URL", "").strip()
        ),
        "state_dir": os.getenv("MARKET_MIND_DR_STATE_DIR", "./data/backups/.state"),
        "timeout_seconds": env_int("MARKET_MIND_DR_TIMEOUT_SECONDS", 300),
        "note": "Values only; URLs and command strings are never printed.",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "cron-line", "systemd", "config"])
    parser.add_argument("--schedule", default="0 2 * * *")
    parser.add_argument("--log-path")
    parser.add_argument("--interval-hours", type=int, default=24)
    parser.add_argument("--on-calendar")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            result = run_once()
            exit_code = 0 if result["status"] == "completed" else 1
        elif args.command == "cron-line":
            result = cron_line(args.schedule, args.log_path)
            exit_code = 0
        elif args.command == "systemd":
            result = systemd_units(args.interval_hours, args.on_calendar)
            exit_code = 0
        else:
            result = effective_config()
            exit_code = 0
    except (DrError, OSError, ValueError) as exc:
        result = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
