"""Verify the integrity digest of an exported historical research JSON bundle."""

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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify the SHA-256 integrity digest in a MARKET-MIND historical research export."
    )
    parser.add_argument("file", help="Path to a downloaded research-evidence JSON file")
    parser.add_argument("--report", help="Optional path to write a detached verification report JSON")
    args = parser.parse_args(argv)
    source_path = Path(args.file)
    try:
        file_bytes = source_path.read_bytes()
        bundle = json.loads(file_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "reason": "file_read_or_json_error", "detail": str(exc)}))
        return 2
    result = verify_bundle(bundle)
    if args.report:
        report_path = Path(args.report)
        if source_path.resolve() == report_path.resolve():
            print(json.dumps({"valid": False, "reason": "report_path_must_not_overwrite_source"}))
            return 2
        report = build_verification_report(source_path, file_bytes, result)
        try:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"valid": False, "reason": "verification_report_write_error", "detail": str(exc)}))
            return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
