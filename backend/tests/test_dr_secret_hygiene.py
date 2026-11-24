"""DR automation must not persist secrets from hooks or exception messages."""
from __future__ import annotations

import argparse
import http.server
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import dr_common  # noqa: E402
from backup_orchestrator import BackupConfig, run_backup  # noqa: E402

SECRET = "DUMMY-SECRET-VALUE-DO-NOT-USE"
TOKEN = "dummy-token-123456789"


def _database(path: Path) -> Path:
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
    return path


class DrSecretHygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.hook = self.root / "chatty_hook.py"
        self.hook.write_text(
            "import os,sys\n"
            "print('hook stdout secret=' + os.environ['DUMMY_SECRET_FOR_TEST'])\n"
            "print('hook stdout token=' + sys.argv[1], file=sys.stderr)\n",
            encoding="utf-8",
        )
        self.env = dict(os.environ, DUMMY_SECRET_FOR_TEST=SECRET,
                        DUMMY_TOKEN_FOR_TEST=TOKEN)

    def test_upload_hook_output_is_redacted_in_result(self):
        result = dr_common.run_upload_command(
            f"{sys.executable} {self.hook} {{sha256}}",
            backup=self.root / "backup.db", sha256="a" * 64, env=self.env,
        )
        self.assertEqual(result["status"], "uploaded")
        text = json.dumps(result)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(TOKEN, text)
        self.assertIn("[REDACTED]", text)

    def test_upload_hook_output_is_redacted_in_manifest(self):
        source = _database(self.root / "market.db")
        args = argparse.Namespace(
            source=source, destination_dir=self.root / "backups",
            state_dir=self.root / "state", retention_days=30, retention_count=None,
            upload_command=f"{sys.executable} {self.hook} {{sha256}}",
            backup=None, dry_run=False, alert_on_success=False,
        )
        with patch.dict(os.environ, {
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": "",
            "MARKET_MIND_DR_ALERT_ON_SUCCESS": "false",
            "MARKET_MIND_BACKUP_KEEP": "",
            "DUMMY_SECRET_FOR_TEST": SECRET,
            "DUMMY_TOKEN_FOR_TEST": TOKEN,
        }):
            result = run_backup(BackupConfig(args))
        self.assertEqual(result["status"], "completed")
        manifest = self.root / "backups" / (Path(result["backup"]).name + ".json")
        text = manifest.read_text(encoding="utf-8") + json.dumps(result)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(TOKEN, text)

    def test_alert_reason_is_redacted(self):
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                received.append(self.rfile.read(length).decode("utf-8"))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        url = f"http://127.0.0.1:{server.server_port}/hook"
        with patch.dict(os.environ, {
            "MARKET_MIND_INCIDENT_WEBHOOK_URL": url,
            "DUMMY_SECRET_FOR_TEST": SECRET,
        }):
            result = dr_common.send_alert("backup_failed", "failed", {
                "reason": f"copy failed: secret={SECRET} token={TOKEN}",
            })
        self.assertEqual(result["status"], "sent")
        self.assertEqual(len(received), 1)
        body = received[0]
        self.assertNotIn(SECRET, body)
        self.assertNotIn(TOKEN, body)
        self.assertIn("copy failed", body)


if __name__ == "__main__":
    unittest.main()
