"""Offline verification for the bounded read-only deployment probe."""
from __future__ import annotations

import http.server
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "load_check.py"


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200
    body = b"secret-response-body-must-never-be-logged"

    def do_GET(self):  # noqa: N802
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_args):
        pass


class LoadCheckTests(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/ready"

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--url", self.url, *args],
            capture_output=True, text=True, timeout=30,
        )

    def test_percentile_and_bounded_report_contain_no_response_body(self):
        result = self._run("--requests", "8", "--concurrency", "4")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["status_counts"], {"200": 8})
        self.assertTrue(report["read_only"])
        self.assertFalse(report["response_bodies_logged"])
        self.assertNotIn("secret-response-body", result.stdout + result.stderr)

    def test_http_failures_are_reported_not_hidden(self):
        _Handler.status = 500
        self.addCleanup(setattr, _Handler, "status", 200)
        result = self._run("--requests", "4", "--concurrency", "2")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["result"], "fail")
        self.assertEqual(report["status_counts"], {"http_500": 4})
        self.assertNotIn("secret-response-body", result.stdout)

    def test_argument_bounds_fail_closed(self):
        for flag, value in (("--requests", "0"), ("--concurrency", "0"),
                            ("--timeout", "0"), ("--max-error-rate", "2")):
            result = self._run(flag, value)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
