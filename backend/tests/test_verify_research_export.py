import hashlib
import json
import unittest
import contextlib
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from verify_research_export import build_batch_report, build_verification_report, main, verify_bundle, verify_file


def signed_bundle():
    payload = {
        "schema_version": "1.1",
        "report_type": "historical_research_evidence",
        "scope": {"symbol": "BTCUSD"},
        "observations": [{"close": 100.5, "source": "user-csv"}],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    payload["integrity"] = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    return payload


class VerifyResearchExportTests(unittest.TestCase):
    def test_builds_detached_report_with_file_hash_and_timestamp(self):
        raw = b'{"schema_version":"1.1"}'
        result = {"valid": True, "reason": "digest_matches"}
        report = build_verification_report(
            "sample-research.json", raw, result, "2026-10-31T10:00:00+00:00"
        )
        self.assertEqual(report["file_name"], "sample-research.json")
        self.assertEqual(report["file_size_bytes"], len(raw))
        self.assertEqual(report["file_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(report["verified_at_utc"], "2026-10-31T10:00:00+00:00")
        self.assertEqual(report["verification"], result)

    def test_batch_report_counts_valid_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            valid_path = Path(directory) / "valid.json"
            altered_path = Path(directory) / "altered.json"
            valid_path.write_text(json.dumps(signed_bundle()), encoding="utf-8")
            altered = signed_bundle()
            altered["observations"][0]["close"] = 999
            altered_path.write_text(json.dumps(altered), encoding="utf-8")
            results = [verify_file(valid_path), verify_file(altered_path)]
            report = build_batch_report(results, "2026-10-31T10:00:00+00:00")
            self.assertEqual(report["files_checked"], 2)
            self.assertEqual(report["valid_count"], 1)
            self.assertEqual(report["invalid_count"], 1)
            self.assertFalse(report["all_valid"])
            self.assertNotIn("file_bytes", report["results"][0])

    def test_batch_cli_writes_report_and_returns_nonzero_for_tampered_file(self):
        with tempfile.TemporaryDirectory() as directory:
            valid_path = Path(directory) / "valid.json"
            altered_path = Path(directory) / "altered.json"
            report_path = Path(directory) / "batch-report.json"
            valid_path.write_text(json.dumps(signed_bundle()), encoding="utf-8")
            altered = signed_bundle()
            altered["scope"]["symbol"] = "ETHUSD"
            altered_path.write_text(json.dumps(altered), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", [
                "verify_research_export.py", str(valid_path), str(altered_path),
                "--batch-report", str(report_path),
            ]):
                with contextlib.redirect_stdout(output):
                    exit_code = main()
            self.assertEqual(exit_code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["files_checked"], 2)
            self.assertEqual(report["valid_count"], 1)
            self.assertEqual(report["invalid_count"], 1)
            self.assertFalse(report["all_valid"])

    def test_batch_cli_reports_unreadable_input_without_aborting_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            valid_path = Path(directory) / "valid.json"
            missing_path = Path(directory) / "missing.json"
            valid_path.write_text(json.dumps(signed_bundle()), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", [
                "verify_research_export.py", str(valid_path), str(missing_path),
            ]):
                with contextlib.redirect_stdout(output):
                    exit_code = main()
            self.assertEqual(exit_code, 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report["files_checked"], 2)
            self.assertEqual(report["valid_count"], 1)
            self.assertEqual(report["invalid_count"], 1)
            self.assertEqual(report["results"][1]["reason"], "file_read_or_json_error")

    def test_cli_writes_detached_report_and_returns_success(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "evidence.json"
            report_path = Path(directory) / "verification.json"
            source.write_text(json.dumps(signed_bundle()), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["verify_research_export.py", str(source), "--report", str(report_path)]):
                with contextlib.redirect_stdout(output):
                    exit_code = main()
            self.assertEqual(exit_code, 0)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["verification"]["valid"])
            self.assertEqual(report["file_name"], "evidence.json")
            self.assertEqual(report["file_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_cli_records_failed_verification_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "tampered.json"
            report_path = Path(directory) / "failed-verification.json"
            bundle = signed_bundle()
            bundle["observations"][0]["close"] = 999
            source.write_text(json.dumps(bundle), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["verify_research_export.py", str(source), "--report", str(report_path)]):
                with contextlib.redirect_stdout(output):
                    exit_code = main()
            self.assertEqual(exit_code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["verification"]["valid"])
            self.assertEqual(report["verification"]["reason"], "digest_mismatch")

    def test_cli_prevents_report_from_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "evidence.json"
            original = json.dumps(signed_bundle())
            source.write_text(original, encoding="utf-8")
            with patch("sys.argv", ["verify_research_export.py", str(source), "--report", str(source)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_accepts_unchanged_export(self):
        result = verify_bundle(signed_bundle())
        self.assertTrue(result["valid"])
        self.assertEqual(result["reason"], "digest_matches")

    def test_detects_modified_observation(self):
        bundle = signed_bundle()
        bundle["observations"][0]["close"] = 101.5
        result = verify_bundle(bundle)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "digest_mismatch")

    def test_detects_modified_provenance(self):
        bundle = signed_bundle()
        bundle["observations"][0]["source"] = "different-source"
        result = verify_bundle(bundle)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "digest_mismatch")

    def test_rejects_missing_or_unsupported_integrity_metadata(self):
        self.assertEqual(verify_bundle({})["reason"], "integrity_metadata_missing")
        bundle = signed_bundle()
        bundle["integrity"]["algorithm"] = "md5"
        self.assertEqual(verify_bundle(bundle)["reason"], "unsupported_integrity_algorithm")

    def test_rejects_malformed_digest_and_non_object_payload(self):
        bundle = signed_bundle()
        bundle["integrity"]["digest"] = "not-a-digest"
        self.assertEqual(verify_bundle(bundle)["reason"], "invalid_digest_format")
        self.assertEqual(verify_bundle([])["reason"], "top_level_json_must_be_an_object")


if __name__ == "__main__":
    unittest.main()
