#!/usr/bin/env python3
"""Verify backups and restore them into a clean environment.

The repository's ``backend/restore_database.py`` performs the atomic, verified
copy. This wrapper adds checksum/manifest verification, a clean-target
requirement, post-restore fingerprint comparison and incident alerting hooks.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from dr_common import (
    DrError, RESTORE_SCRIPT, atomic_write_json, database_fingerprint, env_int,
    iso_now, manifest_path, parse_bool, read_json, run_repo_script, send_alert,
    sha256_file, utcstamp, verify_checksum, write_checksum,
)


class RestoreConfig:
    def __init__(self, args):
        self.backup = Path(args.backup).expanduser().resolve() if args.backup else None
        default_target = os.getenv("MARKET_MIND_RESTORE_TARGET")
        self.target = (
            Path(args.target or default_target).expanduser().resolve()
            if (args.target or default_target)
            else None
        )
        self.overwrite = args.overwrite
        state_dir = args.state_dir or os.getenv("MARKET_MIND_DR_STATE_DIR", "./data/backups/.state")
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.expect_sha256 = (args.expect_sha256 or "").strip().lower() or None
        self.strict = not args.no_strict_compare
        self.alert_on_success = args.alert_on_success or parse_bool(
            os.getenv("MARKET_MIND_DR_ALERT_ON_SUCCESS", "false"),
            "MARKET_MIND_DR_ALERT_ON_SUCCESS",
        )
        self.timeout = env_int("MARKET_MIND_DR_TIMEOUT_SECONDS", 300)


def _check_backup(config: RestoreConfig) -> dict:
    if config.backup is None or not config.backup.is_file():
        raise DrError("backup_file_not_found")
    checksum = verify_checksum(config.backup)
    if checksum["status"] != "verified":
        raise DrError("backup_checksum_failed:" + checksum["status"])
    if config.expect_sha256 and config.expect_sha256 != checksum["sha256"]:
        raise DrError("backup_expected_sha256_mismatch")
    manifest = read_json(manifest_path(config.backup))
    if manifest and manifest.get("sha256") and manifest["sha256"] != checksum["sha256"]:
        raise DrError("backup_manifest_sha256_mismatch")
    return {"checksum": checksum, "manifest": manifest}


def _restore_copy(config: RestoreConfig, destination: Path) -> dict:
    result = run_repo_script(
        RESTORE_SCRIPT,
        [str(config.backup), str(destination), "--overwrite"],
        timeout=config.timeout,
    )
    payload = result["payload"] or {}
    if result["returncode"] != 0 or payload.get("status") != "restored_and_verified":
        raise DrError(
            "restore_script_failed:" + str(payload.get("error") or result["returncode"])
        )
    return payload


def _compare(fingerprint: dict, manifest: dict | None) -> dict:
    if not manifest:
        return {"status": "no_manifest", "compared": False}
    expected = manifest.get("fingerprint") or {}
    if not expected:
        return {"status": "manifest_missing_fingerprint", "compared": False}
    row_diff = {
        table: {
            "backup": expected.get("table_counts", {}).get(table),
            "restored": fingerprint.get("table_counts", {}).get(table),
        }
        for table in sorted(set(expected.get("table_counts", {}))
                            | set(fingerprint.get("table_counts", {})))
        if expected.get("table_counts", {}).get(table)
        != fingerprint.get("table_counts", {}).get(table)
    }
    schema_match = expected.get("schema_version") == fingerprint.get("schema_version")
    backup_digest = expected.get("content_digest")
    restored_digest = fingerprint.get("content_digest")
    content_match = (
        backup_digest is None or restored_digest is None or backup_digest == restored_digest
    )
    fk_ok = not expected.get("foreign_key_violations") and not fingerprint.get("foreign_key_violations")
    return {
        "status": "matched" if not row_diff and schema_match and content_match and fk_ok else "mismatch",
        "compared": True,
        "row_count_differences": row_diff,
        "schema_version_backup": expected.get("schema_version"),
        "schema_version_restored": fingerprint.get("schema_version"),
        "schema_version_match": schema_match,
        "content_digest_backup": backup_digest,
        "content_digest_restored": restored_digest,
        "content_match": content_match,
        "foreign_key_ok": fk_ok,
    }


def verify_backup(config: RestoreConfig) -> dict:
    """Non-destructive verification: checksum, manifest and a scratch restore."""
    checked = _check_backup(config)
    scratch_root = config.state_dir / "verify"
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch = scratch_root / f"{config.backup.stem}-{utcstamp()}.db"
    try:
        payload = _restore_copy(config, scratch)
        fingerprint = database_fingerprint(scratch)
        comparison = _compare(fingerprint, checked["manifest"])
    finally:
        scratch.unlink(missing_ok=True)
    if fingerprint["integrity"] != "ok":
        raise DrError("restored_scratch_integrity_failed:" + fingerprint["integrity"])
    if config.strict and comparison["status"] == "mismatch":
        raise DrError("restored_scratch_fingerprint_mismatch")
    return {
        "status": "verified",
        "backup": str(config.backup),
        "sha256": checked["checksum"]["sha256"],
        "restore_script": payload.get("status"),
        "fingerprint": fingerprint,
        "comparison": comparison,
    }


def restore_backup(config: RestoreConfig) -> dict:
    if config.target is None:
        raise DrError("restore_target_required")
    checked = _check_backup(config)
    if config.target.exists() and any(config.target.iterdir()):
        if not config.overwrite:
            raise DrError("restore_target_not_clean_use_overwrite")
    config.target.mkdir(parents=True, exist_ok=True)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    destination = config.target / "market_mind.db"
    snapshot = None
    if destination.is_file():
        snapshot = config.state_dir / f"pre-restore-{utcstamp()}.db"
        shutil.copy2(destination, snapshot)
        write_checksum(snapshot, sha256_file(snapshot))
    try:
        payload = _restore_copy(config, destination)
        fingerprint = database_fingerprint(destination)
        comparison = _compare(fingerprint, checked["manifest"])
        if fingerprint["integrity"] != "ok":
            raise DrError("restored_database_integrity_failed")
        if config.strict and comparison["status"] == "mismatch":
            raise DrError("restored_database_fingerprint_mismatch")
    except DrError as exc:
        rollback = {"status": "not_required"}
        if snapshot is not None and snapshot.is_file():
            shutil.copy2(snapshot, destination)
            rollback = {"status": "restored", "snapshot": str(snapshot)}
        elif destination.exists():
            destination.unlink(missing_ok=True)
            rollback = {"status": "removed_partial"}
        failed = {
            "status": "failed", "error_type": type(exc).__name__,
            "error": str(exc), "backup": str(config.backup),
            "destination": str(destination), "rollback": rollback,
            "failed_at": iso_now(),
        }
        atomic_write_json(
            config.state_dir / f"restore-report-{utcstamp()}.json", failed
        )
        raise
    report = {
        "status": "restored_and_verified",
        "backup": str(config.backup),
        "destination": str(destination),
        "sha256": checked["checksum"]["sha256"],
        "restore_script": payload.get("status"),
        "fingerprint": fingerprint,
        "comparison": comparison,
        "rollback_snapshot": str(snapshot) if snapshot is not None else None,
        "restored_at": iso_now(),
    }
    atomic_write_json(
        config.state_dir / f"restore-report-{utcstamp()}.json", report
    )
    if config.alert_on_success:
        report["alert"] = send_alert(
            "restore_completed", "ok",
            {"backup": config.backup.name, "destination": str(destination),
             "sha256": checked["checksum"]["sha256"]},
        )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "restore"])
    parser.add_argument("--backup", help="Verified backup file path")
    parser.add_argument("--target", help="Clean target DIRECTORY for restore")
    parser.add_argument("--state-dir")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--expect-sha256")
    parser.add_argument("--no-strict-compare", action="store_true")
    parser.add_argument("--alert-on-success", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = RestoreConfig(args)
        result = verify_backup(config) if args.command == "verify" else restore_backup(config)
        exit_code = 0
    except (DrError, OSError, ValueError) as exc:
        error_type = type(exc).__name__
        result = {"status": "failed", "error_type": error_type, "error": str(exc)}
        result["alert"] = send_alert(
            "restore_failed", "failed", {"error_type": error_type, "reason": str(exc)}
        )
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
