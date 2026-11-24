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


def build_report(root: Path) -> dict:
    root = Path(root)
    backups = sorted(root.glob("market_mind-*.db")) if root.is_dir() else []
    newest_backup = max(backups, key=lambda path: path.stat().st_mtime) if backups else None
    threshold = _integer_env("MARKET_MIND_BACKUP_MAX_AGE_SECONDS", DEFAULT_BACKUP_MAX_AGE_SECONDS)
    age = None
    if newest_backup is not None:
        age = max(0, int(datetime.now(timezone.utc).timestamp() - newest_backup.stat().st_mtime))
    freshness = "never_run" if age is None else ("ok" if age <= threshold else "stale")

    manifest = _newest(root, "market_mind-*.db.json")
    restore = _newest(root, "restore-report-*.json")
    restart = _newest(root, "restart-recovery-*.json")
    sections = {
        "backup": {
            "count": len(backups),
            "newest": str(newest_backup) if newest_backup else None,
            "newest_age_seconds": age,
            "freshness": freshness,
            "max_age_seconds": threshold,
            "integrity": (manifest or {}).get("payload", {}).get("integrity"),
            "sha256": (manifest or {}).get("payload", {}).get("sha256"),
        },
        "restore": {
            "report": (restore or {}).get("path"),
            "status": (restore or {}).get("payload", {}).get("status"),
            "comparison": (restore or {}).get("payload", {}).get("comparison", {}).get("status"),
            "integrity": (restore or {}).get("payload", {}).get("fingerprint", {}).get("integrity"),
        },
        "restart": {
            "report": (restart or {}).get("path"),
            "status": (restart or {}).get("payload", {}).get("status"),
            "stale_locks_removed": (restart or {}).get("payload", {}).get("stale_dr_locks_removed"),
            "requeued": (restart or {}).get("payload", {}).get("interrupted_task_recovery", {})
                         .get("recovery", {}).get("requeued_interrupted_count"),
        },
    }
    complete = bool(backups and manifest and restore and restart)
    return {
        "status": "evidence_complete" if complete else "evidence_incomplete",
        "generated_at": iso_now(),
        "root": str(root),
        "sections": sections,
        "scope": "local_artifacts_only",
        "external_verification": "not_claimed",
        "values_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/backups", help="directory holding DR artifacts")
    args = parser.parse_args()
    print(json.dumps(build_report(Path(args.root)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
