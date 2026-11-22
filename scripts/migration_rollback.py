#!/usr/bin/env python3
"""Armed pre-migration snapshot and rollback path for the research database.

Usage (all operations are explicit; nothing runs automatically):
  prepare  -> create a verified snapshot and an armed rollback plan
  commit   -> mark the plan committed after a successful migration
  rollback -> restore the snapshot into a clean staging dir, then atomically
              replace the target; a copy of the failed target is kept first

This is a research-only platform. No trading, wallet key, signing or order
routing is involved.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from dr_common import (
    DrError, atomic_write_json, iso_now, parse_bool, read_json, run_repo_script,
    send_alert, utcstamp, verify_checksum,
)

ORCHESTRATOR = Path(__file__).with_name("backup_orchestrator.py")
RESTORE_ORCHESTRATOR = Path(__file__).with_name("restore_orchestrator.py")
PLAN_NAME = "migration-rollback-plan.json"


class RollbackConfig:
    def __init__(self, args):
        state_dir = args.state_dir or os.getenv("MARKET_MIND_DR_STATE_DIR", "./data/backups/.state")
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.target = (
            Path(args.target or os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
            .expanduser().resolve()
        )
        self.plan_path = self.state_dir / PLAN_NAME
        self.force = args.force
        self.alert_on_success = args.alert_on_success or parse_bool(
            os.getenv("MARKET_MIND_DR_ALERT_ON_SUCCESS", "false"),
            "MARKET_MIND_DR_ALERT_ON_SUCCESS",
        )


def prepare(config: RollbackConfig) -> dict:
    if not config.target.is_file():
        raise DrError("migration_target_not_found")
    backup_dir = config.state_dir / "migration-backups"
    result = run_repo_script(ORCHESTRATOR, [
        "run",
        "--source", str(config.target),
        "--destination-dir", str(backup_dir),
        "--state-dir", str(config.state_dir / "migration-backup-state"),
        "--retention-days", "7",
        "--retention-count", "3",
    ])
    payload = result["payload"] or {}
    if result["returncode"] != 0 or payload.get("status") != "completed":
        raise DrError("pre_migration_backup_failed")
    plan = {
        "status": "armed",
        "target": str(config.target),
        "backup": payload["backup"],
        "sha256": payload["sha256"],
        "prepared_at": iso_now(),
        "note": "Explicit rollback only; verify the snapshot before migrating.",
    }
    atomic_write_json(config.plan_path, plan)
    return {"status": "armed", "plan": str(config.plan_path),
            "backup": plan["backup"], "sha256": plan["sha256"]}


def commit(config: RollbackConfig) -> dict:
    plan = read_json(config.plan_path)
    if not plan:
        raise DrError("no_rollback_plan")
    if plan.get("status") == "committed":
        return {"status": "already_committed", "plan": str(config.plan_path)}
    plan["status"] = "committed"
    plan["committed_at"] = iso_now()
    atomic_write_json(config.plan_path, plan)
    return {"status": "committed", "plan": str(config.plan_path)}


def rollback(config: RollbackConfig) -> dict:
    plan = read_json(config.plan_path)
    if not plan:
        raise DrError("no_rollback_plan")
    if plan.get("status") != "armed" and not config.force:
        raise DrError("rollback_plan_not_armed_use_force")
    backup = Path(plan.get("backup") or "")
    if not backup.is_absolute():
        backup = config.state_dir / "migration-backups" / backup.name
    checksum = verify_checksum(backup)
    if checksum["status"] != "verified":
        raise DrError("rollback_backup_checksum_failed:" + checksum["status"])
    if plan.get("sha256") and plan["sha256"] != checksum["sha256"]:
        raise DrError("rollback_plan_sha256_mismatch")

    # Preserve the failed migration state for forensics before any replacement.
    failed_snapshot = None
    if config.target.is_file():
        failed_snapshot = config.state_dir / f"failed-migration-{utcstamp()}.db"
        failed_snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.target, failed_snapshot)

    staging = config.state_dir / "rollback-staging" / utcstamp()
    restore_result = run_repo_script(RESTORE_ORCHESTRATOR, [
        "restore", "--backup", str(backup), "--target", str(staging),
        "--overwrite",
    ])
    payload = restore_result["payload"] or {}
    if restore_result["returncode"] != 0 or payload.get("status") != "restored_and_verified":
        raise DrError("rollback_restore_failed")
    staged_db = staging / "market_mind.db"
    if not staged_db.is_file():
        raise DrError("rollback_staged_database_missing")
    os.replace(staged_db, config.target)
    plan["status"] = "rolled_back"
    plan["rolled_back_at"] = iso_now()
    plan["failed_snapshot"] = str(failed_snapshot) if failed_snapshot else None
    atomic_write_json(config.plan_path, plan)
    result = {
        "status": "rolled_back", "target": str(config.target),
        "restored_from": str(backup), "sha256": checksum["sha256"],
        "failed_migration_snapshot": str(failed_snapshot) if failed_snapshot else None,
    }
    if config.alert_on_success:
        result["alert"] = send_alert(
            "migration_rollback_completed", "ok",
            {"backup": backup.name, "destination": str(config.target),
             "sha256": checksum["sha256"]},
        )
    return result


def plan_status(config: RollbackConfig) -> dict:
    plan = read_json(config.plan_path)
    return {"status": "ok", "plan": plan, "plan_path": str(config.plan_path)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "commit", "rollback", "status"])
    parser.add_argument("--target")
    parser.add_argument("--state-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--alert-on-success", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = RollbackConfig(args)
        if args.command == "prepare":
            result = prepare(config)
        elif args.command == "commit":
            result = commit(config)
        elif args.command == "rollback":
            result = rollback(config)
        else:
            result = plan_status(config)
        exit_code = 0
    except (DrError, OSError, ValueError) as exc:
        error_type = type(exc).__name__
        result = {"status": "failed", "error_type": error_type, "error": str(exc)}
        result["alert"] = send_alert(
            "migration_rollback_failed", "failed",
            {"error_type": error_type, "reason": str(exc)},
        )
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
