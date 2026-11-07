import hashlib
import json

"""Compare historical evidence exports without inferring market direction."""

def _check_integrity(bundle):
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
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in expected)
    ):
        return {"valid": False, "reason": "invalid_digest_format"}
    try:
        payload = dict(bundle)
        payload.pop("integrity", None)
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
        "expected_digest": expected.lower(),
        "actual_digest": actual,
    }


def _stable_field_sort_key(field):
    """Order heterogeneous dictionary keys deterministically, including str collisions."""
    return (str(field), type(field).__name__, repr(field))


def _integrity_digest(bundle):
    """Return a digest only when integrity metadata has the expected shape."""
    integrity = bundle.get("integrity")
    digest = integrity.get("digest") if isinstance(integrity, dict) else None
    return digest if isinstance(digest, str) else None


def compare_research_exports(before, after):
    """Compare export scope and observation records by timestamp and source."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("both_inputs_must_be_objects")
    if before.get("report_type") != "historical_research_evidence":
        raise ValueError("unsupported_before_export")
    if after.get("report_type") != "historical_research_evidence":
        raise ValueError("unsupported_after_export")
    old_scope = before.get("scope") or {}
    new_scope = after.get("scope") or {}
    if not isinstance(old_scope, dict) or not isinstance(new_scope, dict):
        raise ValueError("export_scope_must_be_an_object")
    for scope in (old_scope, new_scope):
        if any(
            not isinstance(scope.get(field), str) or not scope[field].strip()
            for field in ("symbol", "interval")
        ):
            raise ValueError("export_scope_symbol_and_interval_required")
    if (old_scope.get("symbol"), old_scope.get("interval")) != (new_scope.get("symbol"), new_scope.get("interval")):
        raise ValueError("export_scope_mismatch")
    def index(bundle):
        indexed = {}
        invalid = 0
        observations = bundle.get("observations", [])
        if not isinstance(observations, list):
            raise ValueError("observations_must_be_a_list")
        for observation in observations:
            if not isinstance(observation, dict):
                invalid += 1
                continue
            timestamp = observation.get("timestamp")
            source = observation.get("source")
            if (
                not isinstance(timestamp, str)
                or not timestamp.strip()
                or not isinstance(source, str)
                or not source.strip()
            ):
                invalid += 1
                continue
            key = (timestamp, source)
            if key in indexed:
                invalid += 1
                continue
            indexed[key] = observation
        return indexed, invalid

    old, old_invalid = index(before)
    new, new_invalid = index(after)
    old_keys, new_keys = set(old), set(new)
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed = []
    for key in sorted(old_keys & new_keys):
        fields = sorted(
            (
                field for field in set(old[key]) | set(new[key])
                if old[key].get(field) != new[key].get(field)
            ),
            key=_stable_field_sort_key,
        )
        if fields:
            changed.append({"timestamp": key[0], "source": key[1], "fields": fields})
    diagnostic_changes = {}
    for section in ("scope", "data_quality", "source_comparison", "timeline", "deep_research"):
        left = before.get(section)
        right = after.get(section)
        if left != right:
            if isinstance(left, dict) and isinstance(right, dict):
                diagnostic_changes[section] = sorted(
                    (
                        key for key in set(left) | set(right)
                        if left.get(key) != right.get(key)
                    ),
                    key=str,
                )
            else:
                diagnostic_changes[section] = ["$"]
    return {
        "different": before != after,
        "scope": old_scope,
        "counts": {
            "before": len(before.get("observations", [])),
            "after": len(after.get("observations", [])),
            "added": len(added), "removed": len(removed), "changed": len(changed),
            "unchanged": len(old_keys & new_keys) - len(changed),
            "invalid_or_duplicate_keys": {"before": old_invalid, "after": new_invalid},
        },
        "added": [{"timestamp": key[0], "source": key[1]} for key in added],
        "removed": [{"timestamp": key[0], "source": key[1]} for key in removed],
        "changed": changed,
        "provenance_changed_fields": [
            field for field in diagnostic_changes.get("scope", [])
            if field in {"source", "sources", "source_sha256", "status", "retrieved_at"}
        ],
        "diagnostic_changed_paths": diagnostic_changes,
        "integrity_digests": {
            "before": _integrity_digest(before),
            "after": _integrity_digest(after),
        },
        "integrity_validation": {
            "before": _check_integrity(before),
            "after": _check_integrity(after),
        },
        "limitations": [
            "Observation keys use exact timestamp strings and source labels.",
            "Duplicate, empty, or malformed keys are reported but cannot be matched.",
            "This comparison does not authenticate a data provider.",
        ],
    }
