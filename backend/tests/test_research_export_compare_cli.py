import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compare_research_exports import main


def export(close):
    return {
        "report_type": "historical_research_evidence",
        "schema_version": "1.1",
        "scope": {"symbol": "BTCUSD", "interval": "1h"},
        "observations": [{"timestamp": "2026-01-01T00:00:00Z", "source": "csv", "close": close}],
    }


class ResearchExportCompareCliTests(unittest.TestCase):
    def test_cli_writes_comparison_report(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            report = Path(directory) / "diff.json"
            before.write_text(json.dumps(export(10)), encoding="utf-8")
            after.write_text(json.dumps(export(12)), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["compare_research_exports.py", str(before), str(after), "--report", str(report)]):
                with contextlib.redirect_stdout(output):
                    code = main()
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["counts"]["changed"], 1)
            self.assertEqual(json.loads(output.getvalue())["counts"]["changed"], 1)

    def test_cli_refuses_to_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            before.write_text(json.dumps(export(10)), encoding="utf-8")
            after.write_text(json.dumps(export(12)), encoding="utf-8")
            original = before.read_text(encoding="utf-8")
            with patch("sys.argv", ["compare_research_exports.py", str(before), str(after), "--report", str(before)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main()
            self.assertEqual(code, 2)
            self.assertEqual(before.read_text(encoding="utf-8"), original)

    def test_cli_returns_error_for_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "missing.json"
            after = Path(directory) / "after.json"
            after.write_text(json.dumps(export(12)), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["compare_research_exports.py", str(before), str(after)]):
                with contextlib.redirect_stdout(output):
                    code = main()
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["error"], "comparison_failed")

    def test_strict_cli_returns_nonzero_for_unverified_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            before.write_text(json.dumps(export(10)), encoding="utf-8")
            after.write_text(json.dumps(export(12)), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["compare_research_exports.py", str(before), str(after), "--strict"]):
                with contextlib.redirect_stdout(output):
                    code = main()
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["comparison_status"], "integrity_unverified")


    def test_strict_cli_still_writes_report_when_integrity_is_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            report = Path(directory) / "strict-report.json"
            before.write_text(json.dumps(export(10)), encoding="utf-8")
            after.write_text(json.dumps(export(12)), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", [
                "compare_research_exports.py", str(before), str(after),
                "--report", str(report), "--strict",
            ]):
                with contextlib.redirect_stdout(output):
                    code = main()
            self.assertEqual(code, 1)
            self.assertTrue(report.exists())
            self.assertEqual(
                json.loads(report.read_text(encoding="utf-8"))["comparison_status"],
                "integrity_unverified",
            )
            self.assertEqual(
                json.loads(output.getvalue())["comparison_status"],
                "integrity_unverified",
            )

    def test_strict_cli_returns_zero_for_verified_compatible_exports(self):
        import hashlib
        def signed(data):
            payload = dict(data)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            payload["integrity"] = {
                "algorithm": "sha256",
                "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "scope": "complete evidence bundle excluding this integrity field",
                "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
            }
            return payload
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            before.write_text(json.dumps(signed(export(10))), encoding="utf-8")
            after.write_text(json.dumps(signed(export(12))), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["compare_research_exports.py", str(before), str(after), "--strict"]):
                with contextlib.redirect_stdout(output):
                    code = main()
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["comparison_status"], "integrity_verified")


if __name__ == "__main__":
    unittest.main()
