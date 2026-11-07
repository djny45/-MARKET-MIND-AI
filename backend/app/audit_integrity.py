"""Canonical SHA-256 integrity helpers for offline JSON audit bundles.

The digest detects accidental or deliberate content changes only when the
expected digest is trusted independently. It does not authenticate the author.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

INTEGRITY_ALGORITHM = "sha256"
INTEGRITY_FIELD = "integrity"


def canonical_json_bytes(bundle: dict[str, Any]) -> bytes:
    """Serialize a bundle deterministically, excluding its integrity envelope."""
    if not isinstance(bundle, dict):
        raise ValueError("audit bundle must be an object")
    payload = {key: value for key, value in bundle.items() if key != INTEGRITY_FIELD}
    try:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("audit bundle must contain finite JSON-compatible values") from exc
    return canonical.encode("utf-8")


def build_integrity_metadata(bundle: dict[str, Any]) -> dict[str, str]:
    """Create integrity metadata for the bundle before the metadata is attached."""
    digest = hashlib.sha256(canonical_json_bytes(bundle)).hexdigest()
    return {
        "algorithm": INTEGRITY_ALGORITHM,
        "canonical_bundle_sha256": digest,
        "scope": "canonical bundle fields excluding this integrity object",
        "authentication": "not_provided",
    }


def verify_integrity_metadata(bundle: dict[str, Any]) -> dict[str, Any]:
    """Verify a bundle's declared digest; report status without claiming authenticity."""
    integrity = bundle.get(INTEGRITY_FIELD) if isinstance(bundle, dict) else None
    if not isinstance(integrity, dict):
        return {"valid": False, "reason": "integrity_metadata_missing"}
    if integrity.get("algorithm") != INTEGRITY_ALGORITHM:
        return {"valid": False, "reason": "unsupported_algorithm"}
    expected = integrity.get("canonical_bundle_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return {"valid": False, "reason": "invalid_digest_format"}
    actual = hashlib.sha256(canonical_json_bytes(bundle)).hexdigest()
    return {
        "valid": actual == expected,
        "reason": "digest_match" if actual == expected else "digest_mismatch",
        "algorithm": INTEGRITY_ALGORITHM,
        "authentication": "not_provided",
    }
