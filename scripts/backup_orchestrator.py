#!/usr/bin/env python3
"""Automated, resumable backup orchestration for the research SQLite database.

Wraps the repository's own verified ``backend/backup_database.py`` and adds:
  * configurable retention by age and/or count,
  * an off-host upload command hook (operator-supplied, no embedded secrets),
  * sha256 sidecars and manifests for integrity verification,
  * a journal + inter-process lock for interrupted-task and restart recovery,
  * best-effort incident webhook alerting via MARKET_MIND_INCIDENT_WEBHOOK_URL.

The platform is research-only; this script never enables trading, wallet keys,
signing or order routing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dr_common import (
    BACKUP_PREFIX, BACKUP_SCRIPT, DrError, DrInterrupted, DrLock, atomic_write_json,
    database_fingerprint, env_int, iso_now, parse_bool, positive_int, read_json,
    run_repo_script, run_upload_command, send_alert, sha256_file, utcstamp,
    verify_checksum, write_checksum,
)

JOURNAL_NAME = "backup-journal.json"


def default_source() -> Path:
    return Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db")).expanduser()


def default_destination() -> Path:
    return Path(
        os.getenv("MARKET_MIND_BACKUP_DIR", "./data/backups")
    ).expanduser()


class BackupConfig:
    def __init__(self, args):
        self.source = Path(args.source).expanduser().resolve() if args.source else default_source().resolve()
        self.destination_dir = (
            Path(args.destination_dir).expanduser().resolve()
            if args.destination_dir else default_destination().resolve()
        )
        state_dir = args.state_dir or os.getenv(
            "MARKET_MIND_DR_STATE_DIR", str(self.destination_dir / ".state")
        )
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.retention_days = (
            positive_int(args.retention_days, "retention_days", minimum=0)
            if args.retention_days is not None
            else positive_int(
                os.getenv("MARKET_MIND_BACKUP_RETENTION_DAYS", "30"),
                "MARKET_MIND_BACKUP_RETENTION_DAYS", minimum=0,
            )
        )
        self.retention_count = (
            positive_int(args.retention_count, "retention_count")
            if args.retention_count is not None
            else None
        )
        env_count = os.getenv("MARKET_MIND_BACKUP_KEEP", "").strip()
        if self.retention_count is None and env_count:
            self.retention_count = positive_int(env_count, "MARKET_MIND_BACKUP_KEEP")
        self.upload_command = (
            args.upload_command
            if args.upload_command is not None
            else os.getenv("MARKET_MIND_BACKUP_UPLOAD_CMD", "")
        )
        self.dry_run = args.dry_run
        self.alert_on_success = args.alert_on_success or parse_bool(
            os.getenv("MARKET_MIND_DR_ALERT_ON_SUCCESS", "false"),
            "MARKET_MIND_DR_ALERT_ON_SUCCESS",
        )
        self.timeout = env_int("MARKET_MIND_DR_TIMEOUT_SECONDS", 300)


def _journal_path(config: BackupConfig) -> Path:
    return config.state_dir / JOURNAL_NAME


def _manifest_path(backup: Path) -> Path:
    return backup.with_name(backup.name + ".json")


def _new_backup_path(config: BackupConfig) -> Path:
    stamp = utcstamp()
    candidate = config.destination_dir / f"{BACKUP_PREFIX}{stamp}.db"
    suffix = 2
    while candidate.exists():
        candidate = config.destination_dir / f"{BACKUP_PREFIX}{stamp}-{suffix}.db"
        suffix += 1
    return candidate


def _set_phase(config: BackupConfig, journal: dict, phase: str, **changes) -> dict:
    journal.update(changes)
    journal["phase"] = phase
    journal["updated_at"] = iso_now()
    atomic_write_json(_journal_path(config), journal)
    return journal


def _create_backup(config: BackupConfig, backup: Path, journal: dict) -> dict:
    """Create + verify a backup through the repository's backup script."""
    if config.dry_run:
        return {"status": "dry_run", "backup": str(backup)}
    result = run_repo_script(
        BACKUP_SCRIPT,
        [str(backup), "--source", str(config.source), "--overwrite"],
        timeout=config.timeout,
    )
    payload = result["payload"] or {}
    if result["returncode"] != 0 or payload.get("status") != "verified":
        raise DrError(
            "backup_script_failed:" + str(payload.get("error") or result["returncode"])
        )
    actual = sha256_file(backup)
    if actual != payload.get("sha256"):
        raise DrError("backup_sha256_mismatch")
    sidecar = write_checksum(backup, actual)
    checksum = verify_checksum(backup, sidecar)
    if checksum["status"] != "verified":
        raise DrError("backup_checksum_verification_failed")
    fingerprint = database_fingerprint(backup)
    if fingerprint["integrity"] != "ok":
        raise DrError("backup_integrity_recheck_failed:" + fingerprint["integrity"])
    manifest = {
        "kind": "market_mind_backup",
        "version": 1,
        "created_at": iso_now(),
        "source": str(config.source),
        "backup": backup.name,
        "sha256": actual,
        "bytes": backup.stat().st_size,
        "integrity": fingerprint["integrity"],
        "fingerprint": fingerprint,
        "retention_days": config.retention_days,
        "retention_count": config.retention_count,
        "upload": {"status": "not_configured"},
    }
    atomic_write_json(_manifest_path(backup), manifest)
    _set_phase(config, journal, "upload", backup=backup.name, sha256=actual,
               backup_bytes=manifest["bytes"])
    return {"status": "verified", "backup": str(backup), "sha256": actual,
            "fingerprint": fingerprint}


def _upload(config: BackupConfig, backup: Path, journal: dict,
            sha256: str | None = None) -> dict:
    if config.dry_run:
        return {"status": "dry_run"}
    if not config.upload_command:
        return {"status": "not_configured"}
    digest = sha256 or sha256_file(backup)
    outcome = run_upload_command(
        config.upload_command, backup=backup, sha256=digest, timeout=config.timeout
    )
    _set_phase(config, journal, "prune", upload=outcome)
    if outcome["status"] != "uploaded":
        raise DrError("offhost_upload_failed:" + str(outcome.get("error_type") or outcome.get("returncode")))
    return outcome


def _backup_age(backup: Path) -> datetime:
    """Parse the UTC stamp from a managed backup name, falling back to mtime."""
    name = backup.name[len(BACKUP_PREFIX):-len(".db")]
    stamp = name.split("-")[0]
    try:
        parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
    except ValueError:
        parsed = datetime.fromtimestamp(backup.stat().st_mtime, timezone.utc).replace(tzinfo=None)
    return parsed.replace(tzinfo=timezone.utc)


def apply_retention(config: BackupConfig, *, keep_backup: Path | None = None) -> dict:
    """Prune stale managed backups and their sidecars; never prune the newest run."""
    if not config.destination_dir.is_dir():
        return {"status": "no_backup_directory", "pruned": []}
    backups = sorted(
        (path for path in config.destination_dir.glob(f"{BACKUP_PREFIX}*.db")
         if path.is_file()),
        key=_backup_age, reverse=True,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.retention_days)
    keep_names = set()
    if keep_backup is not None:
        keep_names.add(keep_backup.name)
    if config.retention_days:
        keep_names.update(
            backup.name for backup in backups if _backup_age(backup) >= cutoff
        )
    if config.retention_count:
        keep_names.update(backup.name for backup in backups[:config.retention_count])
    if not config.retention_days and not config.retention_count:
        keep_names.update(backup.name for backup in backups)
    pruned = []
    for backup in backups:
        if backup.name in keep_names:
            continue
        if config.dry_run:
            pruned.append(backup.name)
            continue
        for path in (backup, backup.with_name(backup.name + ".sha256"),
                     _manifest_path(backup)):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        pruned.append(backup.name)
    orphans = _sweep_orphans(config)
    return {
        "status": "dry_run" if config.dry_run else "completed",
        "candidates": len(backups),
        "retained": len(backups) - len(pruned),
        "pruned": pruned,
        "orphans_removed": orphans,
        "retention_days": config.retention_days,
        "retention_count": config.retention_count,
    }


def _sweep_orphans(config: BackupConfig) -> list[str]:
    """Remove SQLite sidecars and temp files left by earlier backup/restore runs.

    WAL sidecars are never part of a managed backup: the artifact is a single
    ``.db`` file plus its ``.sha256``/``.json`` sidecars. Temp files such as
    ``<backup>.abc123.tmp-shm`` are leftovers from the copy step and would
    otherwise accumulate forever, because retention only prunes ``*.db``.
    """
    patterns = ("*.db-wal", "*.db-shm", "*.db-journal", "*.tmp-wal",
                "*.tmp-shm", "*.tmp-journal", "*.tmp", "*.restore.tmp")
    removed = []
    for pattern in patterns:
        for path in config.destination_dir.glob(pattern):
            if not path.is_file():
                continue
            if config.dry_run:
                removed.append(path.name)
                continue
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                continue
    return sorted(removed)


def _finalize(config: BackupConfig, journal: dict, backup: Path,
              retention: dict) -> dict:
    _set_phase(config, journal, "completed", status="completed", retention=retention)
    summary = {
        "status": "completed",
        "backup": str(backup),
        "sha256": journal.get("sha256"),
        "upload": journal.get("upload"),
        "retention": retention,
    }
    if config.alert_on_success:
        summary["alert"] = send_alert(
            "backup_completed", "ok",
            {"backup": backup.name, "bytes": journal.get("backup_bytes"),
             "sha256": journal.get("sha256")},
        )
    return summary


def _resume(config: BackupConfig, journal: dict) -> dict:
    """Continue an interrupted run from its last verified phase."""
    backup = config.destination_dir / str(journal.get("backup") or "")
    if not journal.get("backup") or not backup.name.startswith(BACKUP_PREFIX):
        raise DrInterrupted("journal_missing_backup_name")
    phase = journal.get("phase")
    if phase in {"backup", "verify"}:
        _set_phase(config, journal, "backup", status="in_progress")
        created = _create_backup(config, backup, journal)
        _upload(config, backup, journal, created["sha256"])
    elif phase == "upload":
        checksum = verify_checksum(backup)
        if checksum["status"] != "verified":
            raise DrInterrupted("resume_checksum_failed")
        _upload(config, backup, journal, checksum["sha256"])
    elif phase == "prune":
        pass
    elif phase == "completed":
        raise DrInterrupted("journal_already_completed_use_run")
    else:
        raise DrInterrupted("unknown_journal_phase:" + str(phase))
    retention = apply_retention(config, keep_backup=backup)
    return _finalize(config, journal, backup, retention)


def _ensure_free_space(directory: Path) -> None:
    """Fail before copying when the backup volume is below the configured floor."""
    if not os.getenv("MARKET_MIND_BACKUP_MIN_FREE_MB", "").strip():
        return
    minimum_mb = env_int("MARKET_MIND_BACKUP_MIN_FREE_MB", 0, minimum=0)
    if minimum_mb <= 0:
        return
    try:
        free_mb = shutil.disk_usage(directory).free // (1024 * 1024)
    except OSError as exc:
        raise DrError("backup_disk_probe_failed:" + type(exc).__name__) from exc
    if free_mb < minimum_mb:
        raise DrError("insufficient_backup_disk_space")


def run_backup(config: BackupConfig, *, resume: bool = False) -> dict:
    config.destination_dir.mkdir(parents=True, exist_ok=True)
    _ensure_free_space(config.destination_dir)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    with DrLock(config.state_dir, "backup"):
        journal = read_json(_journal_path(config))
        if resume:
            if not journal:
                raise DrInterrupted("no_journal_to_resume")
            return _resume(config, journal)
        if journal and journal.get("status") == "in_progress":
            raise DrInterrupted("incomplete_backup_run_use_resume")
        if not config.source.is_file():
            raise DrError("source_database_not_found:" + str(config.source))
        backup = _new_backup_path(config)
        journal = _set_phase(config, {
            "status": "in_progress", "phase": "backup",
            "started_at": iso_now(), "updated_at": iso_now(),
            "source": str(config.source), "backup": backup.name,
            "destination": str(config.destination_dir),
            "resumable": True,
        }, "backup")
        created = _create_backup(config, backup, journal)
        _upload(config, backup, journal, created["sha256"])
        retention = apply_retention(config, keep_backup=backup)
        return _finalize(config, journal, backup, retention)


def retry_upload(config: BackupConfig, backup: Path) -> dict:
    backup = Path(backup).expanduser().resolve()
    checksum = verify_checksum(backup)
    if checksum["status"] != "verified":
        raise DrError("cannot_retry_upload:" + checksum["status"])
    if not config.upload_command:
        raise DrError("no_upload_command_configured")
    journal = read_json(_journal_path(config)) or {
        "status": "in_progress", "phase": "upload", "backup": backup.name,
        "started_at": iso_now(), "updated_at": iso_now(),
    }
    outcome = _upload(config, backup, journal, checksum["sha256"])
    manifest_path = _manifest_path(backup)
    manifest = read_json(manifest_path) or {}
    manifest["upload"] = outcome
    atomic_write_json(manifest_path, manifest)
    return {"status": "upload_retried", "backup": str(backup), "upload": outcome}


def backup_status(config: BackupConfig) -> dict:
    entries = []
    if config.destination_dir.is_dir():
        for backup in sorted(config.destination_dir.glob(f"{BACKUP_PREFIX}*.db")):
            manifest = read_json(_manifest_path(backup)) or {}
            entries.append({
                "backup": backup.name,
                "bytes": backup.stat().st_size if backup.is_file() else 0,
                "checksum": verify_checksum(backup)["status"],
                "manifest_status": manifest.get("status", manifest.get("kind", "missing")),
                "upload": (manifest.get("upload") or {}).get("status"),
                "created_at": manifest.get("created_at"),
            })
    journal = read_json(_journal_path(config))
    return {
        "status": "ok",
        "destination": str(config.destination_dir),
        "retention_days": config.retention_days,
        "retention_count": config.retention_count,
        "backups": entries,
        "journal": journal,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "resume", "retry-upload", "prune", "status"])
    parser.add_argument("--source")
    parser.add_argument("--destination-dir")
    parser.add_argument("--state-dir")
    parser.add_argument("--retention-days", type=int)
    parser.add_argument("--retention-count", type=int)
    parser.add_argument("--upload-command")
    parser.add_argument("--backup", help="Backup path for retry-upload")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--alert-on-success", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = BackupConfig(args)
        if args.command == "run":
            result = run_backup(config)
        elif args.command == "resume":
            result = run_backup(config, resume=True)
        elif args.command == "retry-upload":
            if not args.backup:
                raise DrError("backup_required_for_retry_upload")
            result = retry_upload(config, Path(args.backup))
        elif args.command == "prune":
            result = apply_retention(config)
        else:
            result = backup_status(config)
        exit_code = 0
    except (DrError, OSError, ValueError) as exc:
        error_type = type(exc).__name__
        result = {"status": "failed", "error_type": error_type, "error": str(exc)}
        try:
            result["alert"] = send_alert(
                "backup_failed", "failed", {"error_type": error_type, "reason": str(exc)}
            )
        except (OSError, ValueError):
            result["alert"] = {"status": "delivery_failed"}
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
