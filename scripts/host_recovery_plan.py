#!/usr/bin/env python3
"""Build a read-only host recovery runbook from the checked-in tooling.

This script never touches a host service, Docker daemon, systemd or crontab.
It aggregates existing safe plans (config preflight, generated units, Docker
volume drill) into one operator checklist. Execution remains an external,
authorized activity documented in docs/EXTERNAL-VERIFICATION-CHECKLIST.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import config_preflight
import docker_volume_drill
import install_schedule
from dr_common import redact_secrets

ROOT = Path(__file__).resolve().parents[1]


def _namespace(**values):
    return argparse.Namespace(**values)


def build_plan(root: Path = ROOT) -> dict:
    root = Path(root)
    preflight = config_preflight.build_report(root)
    schedule = install_schedule.build_plan(_namespace(
        output_dir=str(root / "deploy" / "generated"),
        schedule="0 2 * * *", log_path=None, interval_hours=24,
        on_calendar="daily",
        environment_file="/etc/market-mind/market-mind.env",
    ))
    volume = docker_volume_drill.build_plan(_namespace(
        docker="docker", image="<backend-image>",
        source_volume="market_mind_data",
        target_volume="market_mind_data-drill",
        backup_dir=str(root / "data" / "volume-backups"),
    ))
    return {
        "status": "prepared" if preflight["status"] == "pass" else "preflight_failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "read_only_planning_no_privileged_operations",
        "external_verification": "not_claimed",
        "preflight": {
            "status": preflight["status"],
            "failed": preflight["failed"],
        },
        "schedule": {
            "units": sorted(schedule["files"]),
            "environment_file": schedule["files"][install_schedule.BACKUP_SERVICE]
                                .split("EnvironmentFile=", 1)[1].splitlines()[0],
            "commands_not_run": schedule["commands_not_run"],
        },
        "docker_volume": {
            "source_volume": volume["source_volume"],
            "target_volume": volume["target_volume"],
            "command_count": len(volume["commands"]),
            "safety": volume["safety"],
        },
        "manual_steps": [
            "Create /etc/market-mind/market-mind.env with mode 0600.",
            "Review generated units, then install and enable them as root on an authorized host.",
            "Run the kill -9 drill with --stale-after-seconds 1 and capture the restart report.",
            "Run docker_volume_drill.py with --apply, an explicit image and a separate target volume.",
            "Capture recovery_report.py --root <backup-dir> --state-dir <state>.",
        ],
        "rollback": [
            "Disable and stop the generated timer/service units before removing them.",
            "Restore the pre-drill database from a separately verified backup if a drill modifies state.",
            "Remove only the throwaway target volume; never the source volume.",
        ],
        "values_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    report = build_plan(Path(args.root))
    output = redact_secrets(json.dumps(report, indent=2, sort_keys=True))
    print(output)
    return 0 if report["status"] == "prepared" else 1


if __name__ == "__main__":
    sys.exit(main())
