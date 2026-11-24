"""Local fake-Docker tests for the operator volume-drill contract.

No Docker binary is required or invoked here. A shim records argv and simulates
only the mounts/commands the drill uses; real volume execution stays operator work.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "docker_volume_drill.py"


def _shim() -> str:
    return r'''#!/usr/bin/env python3
import json, os, shutil, sqlite3, sys
from pathlib import Path
args = sys.argv[1:]
log = Path(os.environ["FAKE_DOCKER_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\n")

def mounts(argv):
    result = {}
    for index, value in enumerate(argv[:-1]):
        if value == "-v":
            parts = argv[index + 1].split(":")
            host = Path(parts[0])
            if "/" not in parts[0]:
                host = Path(os.environ["FAKE_DOCKER_VOLUME_ROOT"]) / parts[0]
            host.mkdir(parents=True, exist_ok=True)
            result[parts[1]] = host
    return result

if args[:2] == ["volume", "ls"]:
    names = os.environ.get("FAKE_DOCKER_VOLUMES", "").split(",")
    print("\n".join(name for name in names if name))
elif args[:2] in (["volume", "create"], ["volume", "rm"]):
    pass
elif args and args[0] == "run":
    mapping = mounts(args)
    scripts = [a for a in args if a.endswith(".py")]
    if any("backup_database.py" in a for a in scripts):
        target_arg = [a for a in args if a.startswith("/backups/")][0]
        shutil.copy(os.environ["FAKE_DB_FIXTURE"], mapping["/backups"] / Path(target_arg).name)
    elif any("restore_database.py" in a for a in scripts):
        if os.environ.get("FAKE_DOCKER_FAIL_RESTORE"):
            sys.exit(1)
        source_arg = [a for a in args if a.startswith("/backups/")][0]
        shutil.copy(mapping["/backups"] / Path(source_arg).name,
                    mapping["/data"] / "market_mind.db")
    elif "-c" in args:
        if os.environ.get("FAKE_DOCKER_CORRUPT_VERIFY"):
            print(json.dumps({"integrity": "failed", "table_counts": {},
                              "schema_version": None, "bytes": 0,
                              "foreign_key_violations": [], "content_digest": None},
                             sort_keys=True))
        else:
            db = mapping["/data"] / "market_mind.db"
            code = args[args.index("-c") + 1].replace("/data/market_mind.db", str(db))
            exec(code)
else:
    sys.exit(2)
'''


class DockerVolumeDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.log = self.root / "docker.log"
        self.log.touch()
        self.fixture = self.root / "fixture.db"
        with sqlite3.connect(self.fixture) as connection:
            # AUTOINCREMENT creates sqlite_sequence, which the shared host
            # fingerprint excludes; the old duplicated snippet did not.
            connection.execute(
                "CREATE TABLE market_bars (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "symbol TEXT, interval TEXT, timestamp TEXT, "
                "open REAL, high REAL, low REAL, close REAL, volume REAL, status TEXT, "
                "source TEXT, retrieved_at TEXT)"
            )
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
            )
            connection.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')")
        self.shim = self.root / "fake-docker"
        self.shim.write_text(_shim(), encoding="utf-8")
        self.shim.chmod(0o755)
        self.env = dict(os.environ, FAKE_DOCKER_LOG=str(self.log),
                        FAKE_DB_FIXTURE=str(self.fixture), FAKE_DOCKER_VOLUMES="",
                        FAKE_DOCKER_VOLUME_ROOT=str(self.root / "volumes"))
        self.backups = self.root / "backups"
        self.backups.mkdir()

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], env=self.env,
            capture_output=True, text=True, timeout=30,
        )

    def _base(self, command: str):
        return [command, "--docker", str(self.shim), "--image", "fake-backend:latest",
                "--source-volume", "market_mind_data", "--backup-dir", str(self.backups)]

    def test_plan_is_read_only_and_never_touches_the_source(self):
        result = self._run("plan", "--docker", str(self.shim))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "planned")
        self.assertEqual(self.log.read_text(), "")
        commands = payload["commands"]
        self.assertIn("market_mind_data:/data:ro", commands[0])
        self.assertNotEqual(payload["target_volume"], "market_mind_data")
        flat = json.dumps(commands)
        self.assertNotIn("down -v", flat)
        self.assertNotIn("volume rm market_mind_data", flat)

    def test_backup_and_restore_with_fake_docker(self):
        backup = self._run(*self._base("backup"), "--apply")
        self.assertEqual(backup.returncode, 0, backup.stderr)
        manifest = json.loads(backup.stdout)
        self.assertEqual(manifest["status"], "verified")
        backup_path = Path(manifest["backup"])
        self.assertTrue(backup_path.is_file())
        self.assertTrue(backup_path.with_name(backup_path.name + ".sha256").is_file())
        self.assertTrue(backup_path.with_name(backup_path.name + ".json").is_file())

        restore = self._run(*self._base("restore"), "--apply",
                            "--target-volume", "market_mind_data-drill",
                            "--backup", str(backup_path))
        self.assertEqual(restore.returncode, 0, restore.stderr)
        body = json.loads(restore.stdout)
        self.assertEqual(body["status"], "restored_and_verified")
        self.assertEqual(body["comparison"], "matched")
        self.assertEqual(body["restored_fingerprint"], body["expected_fingerprint"])
        calls = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        self.assertTrue(any(call[:2] == ["volume", "create"] and call[-1] == "market_mind_data-drill"
                            for call in calls))
        self.assertTrue(any(call[:2] == ["volume", "rm"] and call[-1] == "market_mind_data-drill"
                            for call in calls))
        self.assertFalse(any("down" in call for call in calls))

    def test_restore_refuses_source_volume_and_existing_target(self):
        same = self._run(*self._base("restore"), "--apply",
                         "--target-volume", "market_mind_data")
        self.assertNotEqual(same.returncode, 0)
        self.assertIn("target_volume_must_differ_from_source", same.stderr + same.stdout)

        env = dict(self.env, FAKE_DOCKER_VOLUMES="occupied")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *self._base("restore"), "--apply",
             "--target-volume", "occupied"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target_volume_already_exists", result.stdout)

    def test_execution_requires_apply(self):
        for command in ("backup", "restore"):
            result = self._run(*self._base(command))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("apply_required", result.stdout)

    def _make_backup(self):
        result = self._run(*self._base("backup"), "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["backup"])

    def test_failed_restore_cleans_up_only_the_temporary_volume(self):
        backup = self._make_backup()
        env = dict(self.env, FAKE_DOCKER_FAIL_RESTORE="1")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *self._base("restore"), "--apply",
             "--target-volume", "market_mind_data-drill", "--backup", str(backup)],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("volume_restore_failed", result.stdout)
        calls = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        self.assertTrue(any(call[:2] == ["volume", "rm"] and call[-1] == "market_mind_data-drill"
                            for call in calls))
        self.assertFalse(any(call[:2] == ["volume", "rm"] and call[-1] == "market_mind_data"
                             for call in calls))

    def test_restore_refuses_a_backup_whose_checksum_no_longer_matches(self):
        backup = self._make_backup()
        backup.write_bytes(b"tampered-after-verification")
        result = self._run(*self._base("restore"), "--apply",
                           "--target-volume", "market_mind_data-drill", "--backup", str(backup))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("backup_checksum_invalid", result.stdout)
        calls = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        self.assertFalse(any(call[:2] == ["volume", "create"] for call in calls))

    def test_fingerprint_mismatch_fails_and_still_removes_the_target(self):
        backup = self._make_backup()
        env = dict(self.env, FAKE_DOCKER_CORRUPT_VERIFY="1")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *self._base("restore"), "--apply",
             "--target-volume", "market_mind_data-drill", "--backup", str(backup)],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("volume_fingerprint_mismatch", result.stdout)
        calls = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        self.assertTrue(any(call[:2] == ["volume", "rm"] for call in calls))

    def test_plan_needs_no_docker_binary(self):
        result = self._run("plan", "--docker", "/nonexistent/docker-binary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "planned")


if __name__ == "__main__":
    unittest.main()
