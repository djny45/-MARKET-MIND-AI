#!/usr/bin/env python3
"""Operator-run Docker named-volume backup and restore drill.

The default ``plan`` mode is read-only and never invokes Docker. ``backup`` and
``restore`` require ``--apply``, an explicit image, and a target volume distinct
from the source. The restore never stops or deletes the running stack and never
runs ``docker compose down -v``: it restores into a separate throwaway volume.

This is a research-only database drill. It does not trade, sign or route orders.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dr_common import (
    REPO_ROOT, DrError, atomic_write_json, database_fingerprint, iso_now,
    sha256_file, utcstamp, verify_checksum, write_checksum,
)

DEFAULT_SOURCE_VOLUME = "market_mind_data"
DEFAULT_PREFIX = "market-mind"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "backup", "restore"))
    parser.add_argument("--apply", action="store_true", help="required to execute anything")
    parser.add_argument("--docker", default=os.getenv("MARKET_MIND_DOCKER_BIN", "docker"))
    parser.add_argument("--image", help="image built from backend/Dockerfile, containing /app/backup_database.py")
    parser.add_argument("--source-volume", default=DEFAULT_SOURCE_VOLUME)
    parser.add_argument("--target-volume", help="separate throwaway volume used only by restore")
    parser.add_argument("--backup-dir", help="host directory for backup artifacts")
    parser.add_argument("--backup", help="existing backup file to restore (defaults to newest in --backup-dir)")
    return parser.parse_args()


def _run(docker: str, argv: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run([docker, *argv], cwd=str(REPO_ROOT), capture_output=True,
                          text=True, timeout=timeout, check=False)


def _require_docker(docker: str) -> None:
    if shutil.which(docker) is None:
        raise DrError("docker_unavailable:" + docker)


def _backup_name() -> str:
    return f"{DEFAULT_PREFIX}-{utcstamp()}.db"


def build_plan(args) -> dict:
    """Describe the exact commands without executing them."""
    image = args.image or "<backend-image>"
    backup_dir = args.backup_dir or str(REPO_ROOT / "data" / "volume-backups")
    name = _backup_name()
    backup_cmd = [
        args.docker, "run", "--rm",
        "-v", f"{args.source_volume}:/data:ro",
        "-v", f"{backup_dir}:/backups",
        image, "python", "/app/backup_database.py", f"/backups/{name}",
        "--source", "/data/market_mind.db",
    ]
    target = args.target_volume or f"{args.source_volume}-restore-{utcstamp()}"
    restore_cmds = []
    if target != args.source_volume:
        restore_cmds = [
            [args.docker, "volume", "create", target],
            [args.docker, "run", "--rm",
             "-v", f"{target}:/data", "-v", f"{backup_dir}:/backups:ro", image,
             "python", "/app/restore_database.py", f"/backups/{name}",
             "/data/market_mind.db", "--overwrite"],
            [args.docker, "volume", "rm", target],
        ]
    return {
        "status": "planned",
        "source_volume": args.source_volume,
        "target_volume": target,
        "backup_dir": backup_dir,
        "backup": str(Path(backup_dir) / name),
        "commands": [backup_cmd, *restore_cmds],
        "requires_apply": True,
        "safety": [
            "source volume mounted read-only for backup",
            "restore targets a separate volume; never the source",
            "no compose down, no volume deletion of the source",
        ],
    }


def run_backup(args) -> dict:
    if not args.apply:
        raise DrError("apply_required")
    if not args.image:
        raise DrError("image_required")
    _require_docker(args.docker)
    plan = build_plan(args)
    backup_dir = Path(plan["backup_dir"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = Path(plan["backup"])
    command = plan["commands"][0]
    completed = _run(args.docker, command[1:])
    if completed.returncode != 0 or not backup.is_file():
        raise DrError("volume_backup_failed:" + str(completed.returncode))
    sidecar = write_checksum(backup, sha256_file(backup))
    checksum = verify_checksum(backup, sidecar)
    fingerprint = database_fingerprint(backup)
    manifest = {
        "status": "verified",
        "kind": "docker_named_volume_backup",
        "created_at": iso_now(),
        "source_volume": args.source_volume,
        "backup": str(backup),
        "checksum": checksum,
        "fingerprint": fingerprint,
        "command": command,
    }
    atomic_write_json(backup.with_name(backup.name + ".json"), manifest)
    return manifest


def run_restore(args) -> dict:
    if not args.apply:
        raise DrError("apply_required")
    if not args.image or not args.target_volume:
        raise DrError("image_and_target_volume_required")
    if args.target_volume == args.source_volume:
        raise DrError("target_volume_must_differ_from_source")
    _require_docker(args.docker)
    existing = _run(args.docker, ["volume", "ls", "-q", "--format", "{{.Name}}"])
    if existing.returncode != 0:
        raise DrError("volume_list_failed:" + str(existing.returncode))
    if args.target_volume in existing.stdout.split():
        raise DrError("target_volume_already_exists")
    backup_dir = Path(args.backup_dir or REPO_ROOT / "data" / "volume-backups")
    backup = Path(args.backup) if args.backup else max(
        backup_dir.glob("*.db"), key=lambda path: path.stat().st_mtime, default=None
    )
    if backup is None or not backup.is_file():
        raise DrError("backup_not_found")
    checksum = verify_checksum(backup)
    if checksum.get("status") != "verified":
        raise DrError("backup_checksum_invalid:" + checksum.get("status", "unknown"))

    created = False
    try:
        create = _run(args.docker, ["volume", "create", args.target_volume])
        if create.returncode != 0:
            raise DrError("target_volume_create_failed")
        created = True
        restore = _run(args.docker, [
            "run", "--rm",
            "-v", f"{args.target_volume}:/data", "-v", f"{backup_dir}:/backups:ro",
            args.image, "python", "/app/restore_database.py", f"/backups/{backup.name}",
            "/data/market_mind.db", "--overwrite",
        ])
        if restore.returncode != 0:
            raise DrError("volume_restore_failed:" + str(restore.returncode))
        report = {
            "status": "restored",
            "kind": "docker_named_volume_restore",
            "restored_at": iso_now(),
            "source_volume": args.source_volume,
            "target_volume": args.target_volume,
            "backup": str(backup),
            "checksum": checksum,
            "note": "Integrity/parity of the restored volume must be verified by the operator before use.",
        }
        atomic_write_json(backup_dir / f"volume-restore-{utcstamp()}.json", report)
        return report
    finally:
        if created:
            _run(args.docker, ["volume", "rm", args.target_volume])


def main() -> int:
    args = _parser()
    try:
        if args.command == "plan":
            result = build_plan(args)
        elif args.command == "backup":
            result = run_backup(args)
        else:
            result = run_restore(args)
    except (DrError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
