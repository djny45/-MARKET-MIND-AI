"""Verify SHA-256 integrity digests in exported historical research JSON bundles."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def verify_bundle(bundle):
    """Return a structured verification result without trusting embedded metadata."""
    if not isinstance(bundle, dict):
        return {"valid": False, "reason": "top_level_json_must_be_an_object"}
    integrity = bundle.get("integrity")
    if not isinstance(integrity, dict):
        return {"valid": False, "reason": "integrity_metadata_missing"}
    if integrity.get("algorithm") != "sha256":
        return {"valid": False, "reason": "unsupported_integrity_algorithm"}
    if integrity.get("scope") != "complete evidence bundle excluding this integrity field":
        return {"valid": False, "reason": "unsupported_integrity_scope"}
    if integrity.get("canonicalization") != "UTF-8 JSON with sorted keys and compact separators":
        return {"valid": False, "reason": "unsupported_canonicalization"}
    expected = integrity.get("digest")
    if not isinstance(expected, str) or len(expected) != 64:
        return {"valid": False, "reason": "invalid_digest_format"}
    try:
        int(expected, 16)
    except ValueError:
        return {"valid": False, "reason": "invalid_digest_format"}

    payload = dict(bundle)
    payload.pop("integrity", None)
    try:
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError):
        return {"valid": False, "reason": "bundle_cannot_be_canonicalized"}
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    valid = actual == expected.lower()
    return {
        "valid": valid,
        "reason": "digest_matches" if valid else "digest_mismatch",
        "algorithm": "sha256",
        "expected_digest": expected.lower(),
        "actual_digest": actual,
        "schema_version": bundle.get("schema_version"),
        "report_type": bundle.get("report_type"),
    }


def build_verification_report(file_path, file_bytes, result, verified_at=None):
    """Create a detached audit record for one verification attempt."""
    timestamp = verified_at or datetime.now(timezone.utc).isoformat()
    return {
        "report_type": "research_export_verification",
        "verified_at_utc": timestamp,
        "file_name": Path(file_path).name,
        "file_size_bytes": len(file_bytes),
        "file_sha256": hashlib.sha256(file_bytes).hexdigest(),
        "verification": result,
        "limitations": [
            "A matching digest detects changes relative to the embedded digest; it is not a digital signature.",
            "This report does not authenticate the original data provider or certify source licensing.",
        ],
    }


def verify_file(file_path):
    """Read and verify one file, retaining file-level errors in the result."""
    source_path = Path(file_path)
    try:
        file_bytes = source_path.read_bytes()
        bundle = json.loads(file_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "file_name": source_path.name,
            "file_path": str(source_path),
            "valid": False,
            "reason": "file_read_or_json_error",
            "detail": str(exc),
            "file_sha256": None,
            "file_size_bytes": None,
            "verification": {"valid": False, "reason": "file_read_or_json_error"},
            "file_bytes": None,
        }
    result = verify_bundle(bundle)
    return {
        "file_name": source_path.name,
        "file_path": str(source_path),
        "valid": result["valid"],
        "reason": result["reason"],
        "file_sha256": hashlib.sha256(file_bytes).hexdigest(),
        "file_size_bytes": len(file_bytes),
        "verification": result,
        "file_bytes": file_bytes,
    }


def build_batch_report(results, verified_at=None):
    """Build a consolidated report without embedding source file contents."""
    checked_at = verified_at or datetime.now(timezone.utc).isoformat()
    rows = [{key: value for key, value in item.items() if key != "file_bytes"} for item in results]
    valid_count = sum(1 for item in results if item["valid"])
    return {
        "report_type": "research_export_batch_verification",
        "verified_at_utc": checked_at,
        "files_checked": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "all_valid": bool(results) and valid_count == len(results),
        "results": rows,
        "limitations": [
            "SHA-256 digests detect changes relative to embedded digests; they are not digital signatures.",
            "Verification does not authenticate original data providers or certify source licensing.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify SHA-256 integrity digests in MARKET-MIND historical research exports."
    )
    parser.add_argument("files", nargs="+", help="One or more downloaded research-evidence JSON files")
    parser.add_argument("--report", help="Detached report path for a single input file")
    parser.add_argument("--batch-report", help="Consolidated report path for multiple input files")
    args = parser.parse_args(argv)

    if len(args.files) == 1 and args.batch_report:
        parser.error("--batch-report requires at least two input files")
    if len(args.files) > 1 and args.report:
        parser.error("--report is for one file; use --batch-report for multiple files")

    report_option = args.report if len(args.files) == 1 else args.batch_report
    input_paths = [Path(item) for item in args.files]
    if report_option:
        report_path = Path(report_option)
        if any(source.resolve() == report_path.resolve() for source in input_paths):
            print(json.dumps({"valid": False, "reason": "report_path_must_not_overwrite_source"}))
            return 2

    results = [verify_file(path) for path in input_paths]
    if len(results) == 1:
        item = results[0]
        output = item["verification"]
        if item["reason"] == "file_read_or_json_error":
            output = {"valid": False, "reason": item["reason"], "detail": item["detail"]}
        if args.report:
            report = build_verification_report(
                input_paths[0], item["file_bytes"] or b"", output
            )
            try:
                Path(args.report).write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                print(json.dumps({"valid": False, "reason": "verification_report_write_error", "detail": str(exc)}))
                return 2
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if item["valid"] else (2 if item["reason"] == "file_read_or_json_error" else 1)

    batch = build_batch_report(results)
    if args.batch_report:
        try:
            Path(args.batch_report).write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(json.dumps({"valid": False, "reason": "batch_report_write_error", "detail": str(exc)}))
            return 2
    print(json.dumps(batch, ensure_ascii=False, indent=2))
    return 0 if batch["all_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
