"""Provider-independent cloud config and authenticated backup encryption."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
CLOUD_CONFIG = SCRIPTS / "cloud_config.py"
BACKUP_CRYPTO = SCRIPTS / "backup_crypto.py"
SECRET = "DUMMY-CLOUD-SECRET-DO-NOT-USE"
KEY = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode()


def cloud_env(**overrides) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("MARKET_MIND_CLOUD_")
           and not k.startswith("MARKET_MIND_S3_")}
    env.update({
        "MARKET_MIND_CLOUD_ENDPOINT": "https://s3.example.invalid",
        "MARKET_MIND_CLOUD_BUCKET": "research-backups",
        "MARKET_MIND_CLOUD_REGION": "us-east-1",
        "MARKET_MIND_CLOUD_ACCESS_KEY": "DUMMYACCESSKEY",
        "MARKET_MIND_CLOUD_SECRET_KEY": SECRET,
        "MARKET_MIND_CLOUD_ENCRYPTION_KEY": KEY,
    })
    env.update(overrides)
    return env


class CloudConfigTests(unittest.TestCase):
    def _run(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(CLOUD_CONFIG), *args],
            cwd=str(ROOT), env=env or cloud_env(), capture_output=True,
            text=True, timeout=30,
        )

    def test_validate_config_fails_closed_without_cloud_or_encryption_config(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("MARKET_MIND_CLOUD_")
               and not k.startswith("MARKET_MIND_S3_")}
        result = self._run("validate-config", env=env)
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        issues = [item["issue"] for item in payload["findings"]]
        self.assertIn("missing_required_variables", issues)
        self.assertIn("encryption_not_configured", issues)
        self.assertFalse(payload["values_exposed"])

    def test_validate_config_passes_with_provider_independent_config(self):
        result = self._run("validate-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["encryption"]["configured"])
        self.assertEqual(payload["encryption"]["source"], "env")
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertNotIn(KEY, result.stdout + result.stderr)

    def test_describe_config_redacts_credentials(self):
        result = self._run("describe-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["bucket"], "research-backups")
        self.assertTrue(payload["credentials_present"])
        self.assertFalse(payload["credentials_exposed"])
        self.assertFalse(payload["values_exposed"])
        self.assertNotIn(SECRET, result.stdout)
        self.assertNotIn(KEY, result.stdout)

    def test_invalid_endpoint_and_encryption_key_fail_closed(self):
        cases = [
            ({"MARKET_MIND_CLOUD_ENDPOINT": "http://s3.remote.invalid"},
             "https_required_outside_loopback"),
            ({"MARKET_MIND_CLOUD_ENDPOINT": "https://user:pw@s3.example.invalid"},
             "must_not_embed_credentials"),
            ({"MARKET_MIND_CLOUD_ENDPOINT": "https://s3.example.invalid/base"},
             "must_not_include_base_path"),
            ({"MARKET_MIND_CLOUD_ENCRYPTION_KEY": "not-a-key"},
             "must_be_base64_aes256_key"),
        ]
        for overrides, expected in cases:
            with self.subTest(expected=expected):
                result = self._run("validate-config", env=cloud_env(**overrides))
                self.assertNotEqual(result.returncode, 0)
                payload = json.loads(result.stdout)
                self.assertIn(expected, [i["issue"] for i in payload["findings"]])
                self.assertNotIn("pw", result.stdout + result.stderr)

    def test_key_file_must_be_mode_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "key"
            path.write_text(KEY)
            os.chmod(path, 0o644)
            result = self._run("validate-config",
                               env=cloud_env(MARKET_MIND_CLOUD_ENCRYPTION_KEY="",
                                             MARKET_MIND_CLOUD_KEY_FILE=str(path)))
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertIn("must_be_a_0600_file", [i["issue"] for i in payload["findings"]])

    def test_upload_requires_complete_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "backup.db.enc"
            source.write_bytes(b"x")
            env = cloud_env()
            env.pop("MARKET_MIND_CLOUD_SECRET_KEY")
            result = self._run("upload", "--file", str(source), env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(SECRET, result.stdout + result.stderr)


class BackupCryptoTests(unittest.TestCase):
    def _run(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(BACKUP_CRYPTO), *args],
            cwd=str(ROOT), env=env or cloud_env(), capture_output=True,
            text=True, timeout=60,
        )

    def test_encrypt_verify_decrypt_roundtrip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plaintext = root / "backup.db"
            payload = b"research-database-fixture" * 100
            plaintext.write_bytes(payload)
            encrypted = root / "backup.db.enc"
            result = self._run("encrypt", "--file", str(plaintext), "--output", str(encrypted))
            self.assertEqual(result.returncode, 0, result.stderr)
            enc_payload = json.loads(result.stdout)
            self.assertEqual(enc_payload["status"], "encrypted")
            self.assertTrue(enc_payload["integrity_verified"])
            self.assertEqual(enc_payload["plaintext_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertNotIn(KEY, result.stdout + result.stderr)

            verify = self._run("verify", "--file", str(encrypted))
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertEqual(json.loads(verify.stdout)["status"], "verified")

            restored = root / "restored.db"
            decrypt = self._run("decrypt", "--file", str(encrypted), "--output", str(restored))
            self.assertEqual(decrypt.returncode, 0, decrypt.stderr)
            self.assertEqual(restored.read_bytes(), payload)

            corrupted = root / "corrupt.db.enc"
            raw = bytearray(encrypted.read_bytes())
            raw[-1] ^= 0xFF
            corrupted.write_bytes(bytes(raw))
            bad = self._run("verify", "--file", str(corrupted))
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(json.loads(bad.stdout)["status"], "integrity_failed")

    def test_local_backup_encrypt_decrypt_and_restore_drill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "market_mind.db"
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE market_bars (symbol TEXT)")
                db.execute("INSERT INTO market_bars VALUES ('BTCUSD')")
                db.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, note TEXT)")
                db.execute("INSERT INTO probe (note) VALUES (?)", ("encrypted-restore",))
                db.commit()

            backup_dir = root / "backups"
            env = cloud_env(
                MARKET_MIND_DB=str(source),
                MARKET_MIND_BACKUP_DIR=str(backup_dir),
                MARKET_MIND_DR_STATE_DIR=str(root / "state"),
            )
            backup = subprocess.run(
                [sys.executable, str(SCRIPTS / "backup_orchestrator.py"), "run"],
                cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(backup.returncode, 0, backup.stderr)
            backup_path = Path(json.loads(backup.stdout)["backup"])
            original_digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()

            encrypted = root / "backup.db.enc"
            enc = self._run("encrypt", "--file", str(backup_path), "--output", str(encrypted), env=env)
            self.assertEqual(enc.returncode, 0, enc.stderr)

            decrypted = root / "decrypted" / "backup.db"
            dec = self._run("decrypt", "--file", str(encrypted), "--output", str(decrypted), env=env)
            self.assertEqual(dec.returncode, 0, dec.stderr)
            self.assertEqual(hashlib.sha256(decrypted.read_bytes()).hexdigest(), original_digest)

            # Restore tooling needs its sidecar/manifest next to the decrypted copy.
            shutil.copy2(backup_path.with_name(backup_path.name + ".json"),
                         decrypted.with_name(decrypted.name + ".json"))
            decrypted.with_name(decrypted.name + ".sha256").write_text(
                f"{original_digest}  {decrypted.name}\n"
            )
            target = root / "restore-target"
            restore = subprocess.run(
                [sys.executable, str(SCRIPTS / "restore_orchestrator.py"), "restore",
                 "--backup", str(decrypted), "--target", str(target)],
                cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(restore.returncode, 0, restore.stderr)
            report = json.loads(restore.stdout)
            self.assertEqual(report["status"], "restored_and_verified")
            self.assertEqual(report["comparison"]["status"], "matched")

            with sqlite3.connect(target / "market_mind.db") as db:
                self.assertEqual(db.execute("SELECT note FROM probe").fetchone()[0],
                                 "encrypted-restore")
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
