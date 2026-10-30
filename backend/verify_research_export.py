"""Verify the integrity digest of an exported historical research JSON bundle."""

import argparse
import hashlib
import json
import sys
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify the SHA-256 integrity digest in a MARKET-MIND historical research export."
    )
    parser.add_argument("file", help="Path to a downloaded research-evidence JSON file")
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "reason": "file_read_or_json_error", "detail": str(exc)}))
        return 2
    result = verify_bundle(bundle)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
