"""Compare historical evidence exports without inferring market direction."""

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
    if (old_scope.get("symbol"), old_scope.get("interval")) != (new_scope.get("symbol"), new_scope.get("interval")):
        raise ValueError("export_scope_mismatch")
    def index(bundle):
        indexed = {}
        invalid = 0
        for observation in bundle.get("observations", []):
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
            if old[key].get(field) != new[key].get(field)
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
                    key for key in set(left) | set(right) if left.get(key) != right.get(key)
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
        "diagnostic_changed_paths": diagnostic_changes,
        "integrity_digests": {
            "before": (before.get("integrity") or {}).get("digest"),
            "after": (after.get("integrity") or {}).get("digest"),
        },
        "limitations": [
            "Observation keys use exact timestamp strings and source labels.",
            "Duplicate or malformed keys are reported but cannot be matched.",
            "This comparison does not authenticate a data provider.",
        ],
    }
