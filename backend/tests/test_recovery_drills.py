"""Tests for backup/DR automation: retention, hooks, resume and rollback drills."""

from __future__ import annotations

import argparse
import http.server
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dr_common  # noqa: E402
from backup_orchestrator import (  # noqa: E402
    BackupConfig, apply_retention, backup_status, run_backup,
)
from backup_scheduler import cron_line, effective_config, systemd_units  # noqa: E402
from migration_rollback import RollbackConfig, commit, prepare, rollback  # noqa: E402
from restore_orchestrator import RestoreConfig, restore_backup, verify_backup  # noqa: E402
from service_restart_recovery import RecoveryConfig, run_recovery  # noqa: E402


def backup_args(**overrides):
    values = {
        "command": "run", "source": None, "destination_dir": None,
        "state_dir": None, "retention_days": None, "retention_count": None,
        "upload_command": None, "backup": None, "dry_run": False,
        "alert_on_success": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def restore_args(**overrides):
    values = {
        "command": "restore", "backup": None, "target": None, "state_dir": None,
        "overwrite": False, "expect_sha256": None, "no_strict_compare": False,
        "alert_on_success": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def rollback_args(**overrides):
    values = {
        "command": "prepare", "target": None, "state_dir": None,
        "force": False, "alert_on_success": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def recovery_args(**overrides):
    values = {
        "command": "run", "db": None, "state_dir": None,
        "stale_after_seconds": None, "skip_task_recovery": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def make_database(path: Path, rows: int = 2) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE market_bars (symbol TEXT, interval TEXT, timestamp TEXT, "
            "open REAL, high REAL, low REAL, close REAL, volume REAL, status TEXT, "
            "source TEXT, retrieved_at TEXT, PRIMARY KEY(symbol,interval,timestamp,source))"
        )
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')"
        )
        for index in range(rows):
            connection.execute(
                "INSERT INTO market_bars VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("BTCUSD", "1d", f"2026-01-0{index + 1}", 1.0, 2.0, 0.5, 1.5,
                 10.0, "synthetic", "fixture", "2026-01-01T00:00:00+00:00"),
            )
    return path


class RecoveryDrillTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)
        patcher = patch.dict(os.environ, {
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "",
            "MARKET_MIND_DR_ALERT_ON_SUCCESS": "false",
            "MARKET_MIND_BACKUP_KEEP": "",
            "MARKET_MIND_BACKUP_RETENTION_DAYS": "30",
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def _config(self, **overrides):
        defaults = {
            "source": self.root / "market.db",
            "destination_dir": self.root / "backups",
            "state_dir": self.root / "state",
            "retention_days": 30,
        }
        defaults.update(overrides)
        return BackupConfig(backup_args(**defaults))

    def test_backup_manifest_checksum_and_clean_restore(self):
        source = make_database(self.root / "market.db")
        config = self._config()
        result = run_backup(config)
        self.assertEqual(result["status"], "completed")
        backup = Path(result["backup"])
        self.assertTrue(backup.is_file())
        self.assertEqual(dr_common.read_checksum(backup.with_name(backup.name + ".sha256")),
                         result["sha256"])

        manifest = json.loads(backup.with_name(backup.name + ".json").read_text())
        self.assertEqual(manifest["sha256"], result["sha256"])
        self.assertEqual(manifest["fingerprint"]["integrity"], "ok")
        self.assertEqual(manifest["fingerprint"]["table_counts"]["market_bars"], 2)

        restored_dir = self.root / "clean-host" / "data"
        restore_result = restore_backup(RestoreConfig(restore_args(
            backup=backup, target=restored_dir, state_dir=self.root / "state",
        )))
        self.assertEqual(restore_result["status"], "restored_and_verified")
        self.assertEqual(restore_result["comparison"]["status"], "matched")
        with sqlite3.connect(restored_dir / "market_mind.db") as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0], 2)

    def test_verify_backup_is_non_destructive(self):
        make_database(self.root / "market.db")
        backup = Path(run_backup(self._config())["backup"])
        result = verify_backup(RestoreConfig(restore_args(
            backup=backup, state_dir=self.root / "state",
        )))
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["fingerprint"]["integrity"], "ok")
        self.assertTrue(backup.is_file())

    def test_restore_rejects_dirty_target_without_overwrite(self):
        make_database(self.root / "market.db")
        backup = Path(run_backup(self._config())["backup"])
        target = self.root / "dirty"
        target.mkdir()
        (target / "keep.txt").write_text("do not erase", encoding="utf-8")
        with self.assertRaisesRegex(dr_common.DrError, "restore_target_not_clean"):
            restore_backup(RestoreConfig(restore_args(
                backup=backup, target=target, state_dir=self.root / "state",
            )))
        self.assertEqual((target / "keep.txt").read_text(), "do not erase")

    def test_checksum_tampering_is_detected(self):
        make_database(self.root / "market.db")
        backup = Path(run_backup(self._config())["backup"])
        sidecar = backup.with_name(backup.name + ".sha256")
        sidecar.write_text("0" * 64 + "  " + backup.name + "\n")
        self.assertEqual(dr_common.verify_checksum(backup)["status"], "checksum_mismatch")
        with self.assertRaisesRegex(dr_common.DrError, "backup_checksum_failed"):
            restore_backup(RestoreConfig(restore_args(
                backup=backup, target=self.root / "clean", state_dir=self.root / "state",
            )))

    def test_retention_by_count_removes_oldest_backups_and_sidecars(self):
        destination = self.root / "backups"
        destination.mkdir()
        for day in (1, 2, 3, 4):
            name = f"market_mind-2026010{day}T000000Z.db"
            backup = destination / name
            backup.write_bytes(b"sqlite placeholder")
            backup.with_name(name + ".sha256").write_text("x")
            backup.with_name(name + ".json").write_text("{}")
        result = apply_retention(BackupConfig(backup_args(
            source=self.root / "market.db", destination_dir=destination,
            state_dir=self.root / "state", retention_days=0, retention_count=2,
        )))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(sorted(result["pruned"]), [
            "market_mind-20260101T000000Z.db", "market_mind-20260102T000000Z.db",
        ])
        remaining = sorted(path.name for path in destination.glob("market_mind-*.db"))
        self.assertEqual(remaining, [
            "market_mind-20260103T000000Z.db", "market_mind-20260104T000000Z.db",
        ])
        self.assertFalse((destination / "market_mind-20260101T000000Z.db.sha256").exists())
        self.assertFalse((destination / "market_mind-20260101T000000Z.db.json").exists())

    def test_retention_sweeps_orphan_wal_and_temp_files(self):
        destination = self.root / "backups"
        destination.mkdir()
        kept = destination / "market_mind-20260104T000000Z.db"
        kept.write_bytes(b"sqlite placeholder")
        kept.with_name(kept.name + ".sha256").write_text("x")
        orphans = [
            kept.with_name(kept.name + "-wal"),
            kept.with_name(kept.name + "-shm"),
            kept.with_name(kept.name + ".abc123.tmp-shm"),
            kept.with_name(kept.name + ".abc123.tmp-wal"),
            kept.with_name(kept.name + ".abc123.restore.tmp"),
        ]
        for orphan in orphans:
            orphan.write_bytes(b"junk")
        result = apply_retention(BackupConfig(backup_args(
            source=self.root / "market.db", destination_dir=destination,
            state_dir=self.root / "state", retention_days=0, retention_count=1,
        )))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["orphans_removed"], sorted(orphan.name for orphan in orphans))
        self.assertTrue(kept.exists())
        self.assertTrue(kept.with_name(kept.name + ".sha256").exists())
        for orphan in orphans:
            self.assertFalse(orphan.exists(), orphan.name)

    def test_retention_dry_run_reports_orphans_without_deleting(self):
        destination = self.root / "backups"
        destination.mkdir()
        kept = destination / "market_mind-20260104T000000Z.db"
        kept.write_bytes(b"sqlite placeholder")
        orphan = kept.with_name(kept.name + "-wal")
        orphan.write_bytes(b"junk")
        result = apply_retention(BackupConfig(backup_args(
            source=self.root / "market.db", destination_dir=destination,
            state_dir=self.root / "state", retention_days=0, retention_count=1,
            dry_run=True,
        )))
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["orphans_removed"], [orphan.name])
        self.assertTrue(orphan.exists())

    def test_offhost_upload_hook_receives_backup_and_sha256(self):
        marker_script = self.root / "upload_hook.py"
        marker_script.write_text(
            "import json,sys,pathlib\n"
            "pathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n",
            encoding="utf-8",
        )
        marker = self.root / "upload-args.json"
        command = f"{sys.executable} {marker_script} {marker} {{backup}} {{sha256}}"
        make_database(self.root / "market.db")
        result = run_backup(self._config(upload_command=command))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["upload"]["status"], "uploaded")
        arguments = json.loads(marker.read_text())
        self.assertEqual(len(arguments), 2)
        self.assertTrue(arguments[0].startswith(str(self.root / "backups")))
        self.assertEqual(len(arguments[1]), 64)

    def test_upload_failure_is_reported_not_silently_ignored(self):
        make_database(self.root / "market.db")
        with self.assertRaisesRegex(dr_common.DrError, "offhost_upload_failed"):
            run_backup(self._config(upload_command=f"{sys.executable} -c exit(7)"))
        journal = json.loads(
            (self.root / "state" / "backup-journal.json").read_text()
        )
        self.assertEqual(journal["status"], "in_progress")
        self.assertEqual(journal["upload"]["status"], "failed")

    def test_interrupted_run_requires_explicit_resume(self):
        make_database(self.root / "market.db")
        config = self._config()
        config.state_dir.mkdir(parents=True, exist_ok=True)
        journal = {
            "status": "in_progress", "phase": "backup",
            "backup": "market_mind-20260101T000000Z.db",
            "started_at": dr_common.iso_now(), "updated_at": dr_common.iso_now(),
        }
        dr_common.atomic_write_json(config.state_dir / "backup-journal.json", journal)
        with self.assertRaisesRegex(dr_common.DrInterrupted, "use_resume"):
            run_backup(config)
        resumed = run_backup(config, resume=True)
        self.assertEqual(resumed["status"], "completed")
        self.assertTrue(Path(resumed["backup"]).is_file())
        self.assertEqual(backup_status(config)["journal"]["status"], "completed")

    def test_lock_recovery_distinguishes_live_and_dead_pids(self):
        state = self.root / "state"
        state.mkdir()
        live = dr_common.DrLock(state, "backup")
        live.acquire()
        try:
            with self.assertRaisesRegex(dr_common.DrLocked, "dr_lock_held"):
                dr_common.DrLock(state, "backup").acquire()
        finally:
            live.release()
        dr_common.atomic_write_json(
            state / "restore.lock", {"pid": 999999, "created_at": dr_common.iso_now()}
        )
        self.assertEqual(dr_common.DrLock(state, "backup").stale_count(), 1)
        self.assertFalse((state / "restore.lock").exists())

    def test_stale_count_reads_each_lock_not_only_self(self):
        """A live lock of another DR process must never be deleted as stale."""
        state = self.root / "state"
        state.mkdir()
        dead_pid = int(subprocess.check_output(
            [sys.executable, "-c", "import os; print(os.getpid())"]
        ).strip())
        dr_common.atomic_write_json(
            state / "backup.lock", {"pid": os.getpid(), "created_at": dr_common.iso_now()}
        )
        dr_common.atomic_write_json(
            state / "restore.lock", {"pid": dead_pid, "created_at": dr_common.iso_now()}
        )
        self.assertEqual(dr_common.DrLock(state, "verify").stale_count(), 1)
        self.assertTrue((state / "backup.lock").exists(), "live lock was wrongly removed")
        self.assertFalse((state / "restore.lock").exists(), "dead lock was not removed")

    def test_lock_recovers_when_the_pid_was_recycled(self):
        """A crashed holder's PID reused by an unrelated process must not block DR forever."""
        state = self.root / "state"
        state.mkdir()
        # PID 1 always exists but its recorded start time cannot match the lock.
        dr_common.atomic_write_json(
            state / "backup.lock",
            {"pid": 1, "pid_start": "1", "created_at": dr_common.iso_now()},
        )
        result = dr_common.DrLock(state, "backup").acquire()
        self.assertEqual(result["status"], "acquired_after_stale_lock_recovery")
        self.assertEqual(result["stale_reason"], "pid_reused_by_other_process")
        self.assertEqual(result["stale_pid"], 1)

    def test_lock_records_an_identity_that_survives_pid_reuse(self):
        state = self.root / "state"
        state.mkdir()
        live = dr_common.DrLock(state, "backup")
        live.acquire()
        try:
            payload = json.loads((state / "backup.lock").read_text(encoding="utf-8"))
            self.assertEqual(payload["pid"], os.getpid())
            self.assertIsNotNone(payload.get("pid_start"))
            self.assertTrue(payload.get("host"))
            with self.assertRaisesRegex(dr_common.DrLocked, "dr_lock_held"):
                dr_common.DrLock(state, "backup").acquire()
            self.assertEqual(dr_common.DrLock(state, "backup").stale_count(), 0)
        finally:
            live.release()

    def test_lock_expires_after_the_max_age_ceiling(self):
        state = self.root / "state"
        state.mkdir()
        dr_common.atomic_write_json(
            state / "backup.lock",
            {"pid": os.getpid(),
             "pid_start": dr_common.DrLock._pid_start(os.getpid()),
             "created_at": "2020-01-01T00:00:00Z"},
        )
        result = dr_common.DrLock(state, "backup", max_age_seconds=60).acquire()
        self.assertEqual(result["stale_reason"], "lock_age_exceeded")

    def test_legacy_lock_without_identity_is_not_reclaimed_while_its_pid_lives(self):
        """Old lock files have no start time: prefer a blocked backup over two at once."""
        state = self.root / "state"
        state.mkdir()
        dr_common.atomic_write_json(
            state / "backup.lock",
            {"pid": os.getpid(), "created_at": dr_common.iso_now()},
        )
        with self.assertRaisesRegex(dr_common.DrLocked, "dr_lock_held"):
            dr_common.DrLock(state, "backup").acquire()

    def test_migration_rollback_restores_pre_migration_state(self):
        target = make_database(self.root / "market.db")
        with sqlite3.connect(target) as connection:
            connection.execute(
                "CREATE TABLE migration_marker (id INTEGER PRIMARY KEY, note TEXT)"
            )
        config = RollbackConfig(rollback_args(
            command="prepare", target=target, state_dir=self.root / "rollback-state",
        ))
        armed = prepare(config)
        self.assertEqual(armed["status"], "armed")
        plan = json.loads(config.plan_path.read_text())
        self.assertEqual(plan["status"], "armed")

        with sqlite3.connect(target) as connection:
            connection.execute("INSERT INTO migration_marker VALUES (1, 'failed migration')")
        committed = commit(config)
        self.assertEqual(committed["status"], "committed")
        with self.assertRaisesRegex(dr_common.DrError, "rollback_plan_not_armed"):
            rollback(config)

        forced = RollbackConfig(rollback_args(
            command="rollback", target=target, state_dir=self.root / "rollback-state",
            force=True,
        ))
        result = rollback(forced)
        self.assertEqual(result["status"], "rolled_back")
        with sqlite3.connect(target) as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM migration_marker"
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertTrue(Path(result["failed_migration_snapshot"]).is_file())

    def test_restart_recovery_clears_stale_locks_and_requeues_tasks(self):
        db = make_database(self.root / "market.db", rows=1)
        state = self.root / "state"
        state.mkdir()
        dr_common.atomic_write_json(
            state / "backup.lock", {"pid": 999999, "created_at": dr_common.iso_now()}
        )
        with sqlite3.connect(db) as connection:
            connection.execute(
                "CREATE TABLE analytical_agent_tasks ("
                "task_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, "
                "task_type TEXT NOT NULL, status TEXT NOT NULL, "
                "input_json TEXT NOT NULL, result_json TEXT NOT NULL, "
                "brain_context_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, execution_attempts INTEGER NOT NULL DEFAULT 0, "
                "execution_token TEXT)"
            )
            connection.execute(
                "CREATE TABLE analytical_agent_task_events ("
                "event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, "
                "worker_id TEXT NOT NULL, event_type TEXT NOT NULL, "
                "from_status TEXT, to_status TEXT, occurred_at TEXT NOT NULL, "
                "detail_json TEXT NOT NULL DEFAULT '{}')"
            )
            connection.execute(
                "INSERT INTO analytical_agent_tasks VALUES "
                "('task-1','worker-1','research_brief','running','{}','{}','sha',"
                "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00',0,NULL)"
            )
        result = run_recovery(RecoveryConfig(recovery_args(
            db=db, state_dir=state, stale_after_seconds=900,
        )))
        self.assertEqual(result["status"], "recovered")
        self.assertEqual(result["stale_dr_locks_removed"], 1)
        self.assertEqual(result["database_integrity"]["status"], "ok")
        self.assertEqual(result["interrupted_task_recovery"]["recovery"]["requeued_interrupted_count"], 1)
        with sqlite3.connect(db) as connection:
            self.assertEqual(connection.execute(
                "SELECT status FROM analytical_agent_tasks WHERE task_id='task-1'"
            ).fetchone()[0], "queued")

    def test_alert_webhook_is_best_effort_and_never_carries_secrets(self):
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                received.append((self.path, self.rfile.read(length).decode("utf-8")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        url = f"http://127.0.0.1:{server.server_port}/hook?token=do-not-log"
        with patch.dict(os.environ, {"MARKET_MIND_INCIDENT_WEBHOOK_URL": url}):
            result = dr_common.send_alert("backup_failed", "failed", {
                "reason": "disk-full", "password": "hunter2", "api_key": "abc123",
            })
        self.assertEqual(result["status"], "sent")
        self.assertEqual(len(received), 1)
        path, body = received[0]
        self.assertIn("do-not-log", path)
        self.assertNotIn("do-not-log", body)
        self.assertNotIn("hunter2", body)
        self.assertNotIn("abc123", body)
        self.assertNotIn("password", body)
        self.assertNotIn("api_key", body)
        self.assertIn("disk-full", body)
        with patch.dict(os.environ, {"MARKET_MIND_INCIDENT_WEBHOOK_URL": ""}):
            self.assertEqual(dr_common.send_alert("x", "failed")["status"], "disabled")

    def test_scheduler_hooks_generate_without_installing(self):
        with self.assertRaisesRegex(dr_common.DrError, "cron_schedule_must_have_5_fields"):
            cron_line("* * *", None)
        line = cron_line("0 2 * * *", "/var/log/market-mind-backup.log")
        self.assertIn("0 2 * * *", line["line"])
        self.assertIn("backup_scheduler.py run", line["line"])
        units = systemd_units(24, None)
        self.assertIn("OnUnitActiveSec=24h", units["timer"])
        self.assertIn("Type=oneshot", units["service"])
        with patch.dict(os.environ, {
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "https://example.invalid/hook?token=secret"
        }):
            config = effective_config()
        self.assertTrue(config["incident_webhook_configured"])
        self.assertNotIn("secret", json.dumps(config))


if __name__ == "__main__":
    unittest.main()
