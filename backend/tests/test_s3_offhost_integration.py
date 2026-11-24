"""Local S3-compatible integration drill for the stdlib off-host adapter.

This is a *local* compatibility test against an in-process fake S3 endpoint.
It verifies real SigV4 signing, byte/SHA-256 parity and fail-closed downloads.
It does NOT claim that a real S3 bucket, credentials or a cloud restore exist.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "s3_offhost.py"
BUCKET = "research-backups"
REGION = "us-east-1"
ACCESS_KEY = "DUMMYACCESSKEY"
SECRET_KEY = "DUMMYSECRETKEY-DO-NOT-USE"


class _FakeS3Handler(BaseHTTPRequestHandler):
    objects: dict[str, bytes] = {}

    def log_message(self, *_args):
        pass

    def _signature_is_valid(self, method: str, body: bytes) -> bool:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith(f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/"):
            return False
        try:
            supplied = auth.rsplit("Signature=", 1)[1].strip()
        except IndexError:
            return False
        amzdate = self.headers.get("x-amz-date", "")
        payload_hash = self.headers.get("x-amz-content-sha256", "")
        if len(amzdate) != 16 or payload_hash != hashlib.sha256(body).hexdigest():
            return False
        scope = f"{amzdate[:8]}/{REGION}/s3/aws4_request"
        canonical = "\n".join([
            method, self.path, "",
            f"host:{self.headers.get('Host', '')}\n"
            f"x-amz-content-sha256:{payload_hash}\nx-amz-date:{amzdate}\n",
            "host;x-amz-content-sha256;x-amz-date", payload_hash,
        ])
        to_sign = "\n".join([
            "AWS4-HMAC-SHA256", amzdate, scope,
            hashlib.sha256(canonical.encode()).hexdigest(),
        ])

        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        key = sign(("AWS4" + SECRET_KEY).encode(), amzdate[:8])
        key = sign(key, REGION)
        key = sign(key, "s3")
        key = sign(key, "aws4_request")
        expected = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, supplied) and f"/{scope}" in auth

    def do_PUT(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if not self._signature_is_valid("PUT", body):
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.objects[self.path] = body
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        body = self.objects.get(self.path)
        if body is None:
            self.send_response(404)
            self.send_header("Content-Length", "15")
            self.end_headers()
            self.wfile.write(b"NoSuchKeyBody!!")
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class S3OffhostIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _FakeS3Handler.objects.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeS3Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        endpoint = f"http://127.0.0.1:{self.server.server_port}"
        self.env = dict(os.environ, **{
            "MARKET_MIND_S3_ENDPOINT": endpoint,
            "MARKET_MIND_S3_BUCKET": BUCKET,
            "MARKET_MIND_S3_REGION": REGION,
            "MARKET_MIND_S3_ACCESS_KEY": ACCESS_KEY,
            "MARKET_MIND_S3_SECRET_KEY": SECRET_KEY,
            "MARKET_MIND_S3_PREFIX": "market-mind/backups",
        })

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def _run(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=env or self.env, capture_output=True, text=True, timeout=20,
        )

    def test_upload_download_roundtrip_verifies_signature_and_parity(self):
        source = self.root / "backup.db"
        payload = b"SQLite backup fixture\n" + bytes(range(256)) * 4
        source.write_bytes(payload)
        key = "market-mind/backups/integration.db"

        uploaded = self._run("upload", "--file", str(source), "--key", key)
        self.assertEqual(uploaded.returncode, 0, uploaded.stderr)
        self.assertEqual(json.loads(uploaded.stdout)["status"], 200)
        self.assertNotIn(SECRET_KEY, uploaded.stdout + uploaded.stderr)

        stored = _FakeS3Handler.objects[f"/{BUCKET}/{key}"]
        self.assertEqual(hashlib.sha256(stored).hexdigest(), hashlib.sha256(payload).hexdigest())

        destination = self.root / "restored.db"
        downloaded = self._run("download", "--file", str(destination), "--key", key)
        self.assertEqual(downloaded.returncode, 0, downloaded.stderr)
        self.assertEqual(destination.read_bytes(), payload)
        self.assertNotIn(SECRET_KEY, downloaded.stdout + downloaded.stderr)

    def test_wrong_secret_is_rejected_and_reports_failure(self):
        source = self.root / "backup.db"
        source.write_bytes(b"fixture")
        env = dict(self.env, MARKET_MIND_S3_SECRET_KEY="WRONG-SECRET")
        result = self._run("upload", "--file", str(source),
                           "--key", "market-mind/backups/wrong.db", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], 403)
        self.assertNotIn("WRONG-SECRET", result.stdout + result.stderr)

    def test_failed_download_does_not_overwrite_an_existing_file(self):
        destination = self.root / "existing.db"
        original = b"previous verified backup"
        destination.write_bytes(original)
        result = self._run("download", "--file", str(destination),
                           "--key", "market-mind/backups/missing.db")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
