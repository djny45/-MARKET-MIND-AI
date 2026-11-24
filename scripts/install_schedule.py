#!/usr/bin/env python3
"""Generate host schedule files for backup and restart recovery.

This is SCAFFOLDING, not installation. The default ``plan`` mode writes nothing
and never invokes systemctl/crontab. ``apply`` writes only into a caller-chosen
output directory; an operator must review and install the files on an authorized
host. Secrets stay in a 0600 EnvironmentFile that this script never creates.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from backup_scheduler import cron_line, systemd_units
from dr_common import DrError, REPO_ROOT, atomic_write_json, iso_now

RESTART_SERVICE = "market-mind-restart-recovery.service"
BACKUP_SERVICE = "market-mind-backup.service"
BACKUP_TIMER = "market-mind-backup.timer"
CRON_FILE = "market-mind-backup.cron"
PROTECTED_PREFIXES = ("/etc", "/usr/lib", "/var/spool/cron", "/lib/systemd")


def _restart_unit() -> str:
    script = REPO_ROOT / "scripts" / "service_restart_recovery.py"
    return "\n".join([
        "[Unit]",
        "Description=MARKET-MIND post-restart stale-lock and task recovery",
        "After=network-online.target",
        "",
        "[Service]",
        "Type=oneshot",
        f"WorkingDirectory={REPO_ROOT}",
        f"ExecStart={shlex.quote(sys.executable)} {shlex.quote(str(script))} run",
        "# Requires MARKET_MIND_DB and MARKET_MIND_DR_STATE_DIR from a 0600 EnvironmentFile.",
        "# This unit requeues interrupted tasks without dispatching them.",
        "",
    ])


def build_plan(args) -> dict:
    cron = cron_line(args.schedule, args.log_path)
    units = systemd_units(args.interval_hours, args.on_calendar)
    files = {
        BACKUP_SERVICE: units["service"],
        BACKUP_TIMER: units["timer"],
        RESTART_SERVICE: _restart_unit(),
        CRON_FILE: cron["line"] + "\n",
    }
    return {
        "status": "planned",
        "generated_at": iso_now(),
        "output_dir": str(Path(args.output_dir).expanduser().resolve()),
        "files": {name: content for name, content in files.items()},
        "requires_apply": True,
        "commands_not_run": ["systemctl", "crontab", "systemctl enable"],
        "secret_policy": "Secrets must be supplied by an operator-owned 0600 EnvironmentFile.",
    }


def _guard_output_dir(path: Path, *, allow_system_paths: bool) -> None:
    resolved = path.resolve()
    if not allow_system_paths and any(
        str(resolved) == prefix or str(resolved).startswith(prefix + "/")
        for prefix in PROTECTED_PREFIXES
    ):
        raise DrError("system_path_requires_allow_system_paths")


def apply_plan(args) -> dict:
    if not args.apply:
        raise DrError("apply_required")
    _guard_output_dir(Path(args.output_dir), allow_system_paths=args.allow_system_paths)
    plan = build_plan(args)
    directory = Path(plan["output_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, content in plan["files"].items():
        path = directory / name
        path.write_text(content, encoding="utf-8")
        written[name] = str(path)
    summary = {key: value for key, value in plan.items() if key != "files"}
    summary.update({"status": "written", "files_written": written, "files": None})
    atomic_write_json(directory / "install-plan.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--output-dir", default="deploy/generated")
    parser.add_argument("--schedule", default="0 2 * * *")
    parser.add_argument("--log-path")
    parser.add_argument("--interval-hours", type=int, default=24)
    parser.add_argument("--on-calendar")
    parser.add_argument("--apply", action="store_true", help="required to write files")
    parser.add_argument("--allow-system-paths", action="store_true",
                        help="explicit opt-in before writing under /etc or other system paths")
    args = parser.parse_args()
    try:
        result = build_plan(args) if args.command == "plan" else apply_plan(args)
    except (DrError, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
