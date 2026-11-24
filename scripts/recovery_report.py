#!/usr/bin/env python3
"""Aggregate local backup, restore and restart-recovery evidence.

Read-only: it inspects artifacts produced by the DR orchestration scripts and
emits a compact report for operators. It does not run a restore, contact a
remote service, or claim that external infrastructure was exercised.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dr_common import iso_now, read_json

# Matches backend/app/main.py backup-freshness default; kept local so this
# read-only operator script has no application imports.
DEFAULT_BACKUP_MAX_AGE_SECONDS = 90000


def _newest(directory: Path, pattern: str) -> dict | None:
    if not directory.is_dir():
        return None
    paths = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return None
    payload = read_json(paths[0])
    return {"path": str(paths[0]), "payload": payload} if payload else None


def _integer_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if 1 <= value <= 31536000 else default


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _find_artifact(directories: list[Path], pattern: str) -> dict | None:
    for directory in directories:
        found = _newest(directory, pattern)
        if found:
            return found
    return None


def build_report(root: Path, state_dir: Path | None = None) -> dict:
    root = Path(root)
    state = Path(state_dir) if state_dir is not None else root / ".state"
    search_dirs = [root] if state.resolve() == root.resolve() else [root, state]
    backups = sorted(root.glob("market_mind-*.db")) if root.is_dir() else []
    newest_backup = max(backups, key=lambda path: path.stat().st_mtime) if backups else None
    threshold = _integer_env("MARKET_MIND_BACKUP_MAX_AGE_SECONDS", DEFAULT_BACKUP_MAX_AGE_SECONDS)
    age = None
    if newest_backup is not None:
        age = max(0, int(datetime.now(timezone.utc).timestamp() - newest_backup.stat().st_mtime))
    freshness = "never_run" if age is None else ("ok" if age <= threshold else "stale")

    manifest = None
    if newest_backup is not None:
        sidecar = newest_backup.with_name(newest_backup.name + ".json")
        payload = read_json(sidecar)
        if payload:
            manifest = {"path": str(sidecar), "payload": payload}
    restore = _find_artifact(search_dirs, "restore-report-*.json")
    restart = _find_artifact(search_dirs, "restart-recovery-*.json")
    journal = _find_artifact(search_dirs, "recovery-journal.json")
    journal_status = _as_dict((journal or {}).get("payload")).get("status")
    interrupted_previous_run = journal_status in {"in_progress", "failed"}

    backup_payload = _as_dict((manifest or {}).get("payload"))
    restore_payload = _as_dict((restore or {}).get("payload"))
    restart_payload = _as_dict((restart or {}).get("payload"))
    restore_comparison = _as_dict(restore_payload.get("comparison"))
    restore_fingerprint = _as_dict(restore_payload.get("fingerprint"))
    requeue = _as_dict(_as_dict(restart_payload.get("interrupted_task_recovery")).get("recovery"))

    backup_ok = backup_payload.get("integrity") == "ok" and bool(backup_payload.get("sha256"))
    restore_ok = (
        restore_payload.get("status") == "restored_and_verified"
        and restore_comparison.get("status") == "matched"
        and restore_fingerprint.get("integrity") == "ok"
    )
    restart_ok = restart_payload.get("status") == "recovered"
    restore_backup_name = Path(str(restore_payload.get("backup") or "")).name
    paired = (
        newest_backup is not None
        and restore_backup_name == newest_backup.name
        and (
            not backup_payload.get("sha256")
            or restore_payload.get("sha256") == backup_payload.get("sha256")
        )
    )
    complete = bool(backups and backup_ok and restore_ok and restart_ok and paired)

    sections = {
        "backup": {
            "count": len(backups),
            "newest": str(newest_backup) if newest_backup else None,
            "newest_age_seconds": age,
            "freshness": freshness,
            "max_age_seconds": threshold,
            "integrity": backup_payload.get("integrity"),
            "sha256": backup_payload.get("sha256"),
            "evidence_valid": backup_ok,
        },
        "restore": {
            "report": (restore or {}).get("path"),
            "status": restore_payload.get("status"),
            "comparison": restore_comparison.get("status"),
            "integrity": restore_fingerprint.get("integrity"),
            "evidence_valid": restore_ok,
            "paired_to_newest_backup": paired,
        },
        "restart": {
            "report": (restart or {}).get("path"),
            "status": restart_payload.get("status"),
            "stale_locks_removed": restart_payload.get("stale_dr_locks_removed"),
            "requeued": requeue.get("requeued_interrupted_count"),
            "evidence_valid": restart_ok,
            "journal_status": journal_status,
            "interrupted_previous_run": interrupted_previous_run,
        },
    }
    return {
        "status": "evidence_complete" if complete else "evidence_incomplete",
        "generated_at": iso_now(),
        "root": str(root),
        "state_dir": str(state),
        "sections": sections,
        "scope": "local_artifacts_only",
        "external_verification": "not_claimed",
        "values_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/backups", help="directory holding backup artifacts")
    parser.add_argument("--state-dir", help="directory holding restore/restart reports (default: <root>/.state)")
    args = parser.parse_args()
    report = build_report(Path(args.root), Path(args.state_dir) if args.state_dir else None)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "evidence_complete" else 1


if __name__ == "__main__":
    sys.exit(main())
