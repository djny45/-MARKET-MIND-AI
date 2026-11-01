"""Snapshot-bound holdout forecast evaluation with verified dataset boundaries."""
from datetime import datetime, timezone

from .forecast_evaluation import evaluate_heldout_forecasts


def _instant(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_snapshot_forecasts(snapshot, verification, records):
    """Require a verified snapshot and keep forecast origins/targets in its holdout."""
    if not isinstance(snapshot, dict) or not isinstance(verification, dict):
        raise ValueError("snapshot and verification records are required")
    if verification.get("status") != "verified":
        raise ValueError("snapshot integrity verification must pass before evaluation")
    snapshot_id = snapshot.get("snapshot_id")
    if not isinstance(snapshot_id, str) or len(snapshot_id) != 64:
        raise ValueError("snapshot must have a valid snapshot_id")
    manifest = snapshot.get("manifest")
    source_manifests = manifest.get("source_manifests") if isinstance(manifest, dict) else None
    if not isinstance(source_manifests, dict):
        raise ValueError("snapshot manifest has no source manifests")
    if not isinstance(records, list) or not 3 <= len(records) <= 10000:
        raise ValueError("records must contain between 3 and 10000 holdout observations")

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} must be an object")
        source = record.get("source")
        source_manifest = source_manifests.get(source) if isinstance(source, str) else None
        if not isinstance(source_manifest, dict) or source_manifest.get("status") != "ready":
            raise ValueError(f"record {index} source must identify a ready snapshot source")
        holdout = source_manifest.get("partitions", {}).get("holdout")
        if not isinstance(holdout, dict):
            raise ValueError(f"record {index} source has no holdout partition")
        first = _instant(holdout.get("first_timestamp_utc"))
        last = _instant(holdout.get("last_timestamp_utc"))
        origin = _instant(record.get("origin_timestamp"))
        target = _instant(record.get("target_timestamp"))
        if None in (first, last, origin, target):
            raise ValueError(f"record {index} has invalid timezone-aware holdout timestamps")
        if origin < first or origin > last or target < first or target > last:
            raise ValueError(f"record {index} origin and target must both fall inside the snapshot holdout range")

    result = evaluate_heldout_forecasts(records)
    return {
        **result,
        "snapshot": {
            "snapshot_id": snapshot_id,
            "manifest_sha256": snapshot.get("manifest_sha256"),
            "dataset_sha256": snapshot.get("dataset_sha256"),
            "integrity_status": verification.get("status"),
        },
        "methodology": [
            "The referenced snapshot manifest and captured dataset payload must pass digest verification before scoring.",
            "Every forecast source must be a ready source in that snapshot; origin and target timestamps must lie inside its holdout range.",
            "Forecast values, realized returns and source references remain caller-supplied and are not independently authenticated.",
            "This binds the evaluation report to a reproducible dataset snapshot; it does not establish predictive performance outside this sample.",
        ],
        "research_only": True,
    }
