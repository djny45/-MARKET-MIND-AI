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
    if not isinstance(expected, str) or len(expected) != 64:
        return {"valid": False, "reason": "invalid_digest_format"}
    try:
        int(expected, 16)
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


def _field_changed(left, right, key):
    """Distinguish an absent field from a field explicitly set to None."""
    return (key in left) != (key in right) or left.get(key) != right.get(key)


def _integrity_digest(bundle):
    integrity = bundle.get("integrity")
    return integrity.get("digest") if isinstance(integrity, dict) else None


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
            if not isinstance(timestamp, str) or not isinstance(source, str):
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
            field for field in set(old[key]) | set(new[key])
            if _field_changed(old[key], new[key], field)
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
                    key for key in set(left) | set(right) if _field_changed(left, right, key)
                )
            else:
                diagnostic_changes[section] = ["$"]
    integrity_validation = {
        "before": _check_integrity(before),
        "after": _check_integrity(after),
    }
    integrity_results = (integrity_validation["before"], integrity_validation["after"])
    if any(result.get("reason") == "digest_mismatch" for result in integrity_results):
        comparison_status = "integrity_failed"
    elif any(not result.get("valid") for result in integrity_results):
        comparison_status = "integrity_unverified"
    elif old_invalid or new_invalid:
        comparison_status = "observation_keys_incomplete"
    else:
        comparison_status = "integrity_verified"

    return {
        "comparison_status": comparison_status,
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
            if field in {"source", "sources", "status", "retrieved_at"}
        ],
        "diagnostic_changed_paths": diagnostic_changes,
        "integrity_digests": {
            "before": _integrity_digest(before),
            "after": _integrity_digest(after),
        },
        "integrity_validation": integrity_validation,
        "limitations": [
            "Observation keys use exact timestamp strings and source labels.",
            "Duplicate or malformed keys are reported but cannot be matched.",
            "This comparison does not authenticate a data provider.",
        ],
    }
