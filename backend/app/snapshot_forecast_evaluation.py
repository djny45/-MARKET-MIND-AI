"""Evaluate forecasts against an integrity-checked historical evaluation snapshot."""
from datetime import datetime, timezone
import math

from .forecast_evaluation import evaluate_heldout_forecasts


def _instant(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def evaluate_snapshot_forecasts(snapshot, records):
    """Derive realized returns from a verified snapshot's own OHLCV bars."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("manifest"), dict):
        raise ValueError("a valid evaluation snapshot is required")
    if not isinstance(records, list) or not 3 <= len(records) <= 10000:
        raise ValueError("records must contain between 3 and 10000 holdout observations")

    manifest = snapshot["manifest"]
    if manifest.get("ready_source_count", 0) < 1:
        raise ValueError("snapshot has no ready source datasets")
    by_source = {}
    for index, bar in enumerate(snapshot.get("dataset_bars", [])):
        if not isinstance(bar, dict):
            raise ValueError(f"snapshot bar {index} must be an object")
        source = str(bar.get("source") or "unknown")
        instant = _instant(bar.get("timestamp"), "snapshot bar timestamp")
        try:
            close = float(bar.get("close"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"snapshot bar {index} close must be finite and positive") from exc
        if not math.isfinite(close) or close <= 0:
            raise ValueError(f"snapshot bar {index} close must be finite and positive")
        key = instant
        if key in by_source.setdefault(source, {}):
            raise ValueError(f"snapshot contains duplicate timestamps for source {source}")
        by_source[source][key] = close

    evaluated_records = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} must be an object")
        if record.get("partition") != "holdout":
            raise ValueError(f"record {index} must belong to the holdout partition")
        source = record.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"record {index} requires a source matching the snapshot")
        source = source.strip()
        source_manifest = manifest.get("source_manifests", {}).get(source)
        if not source_manifest or source_manifest.get("status") != "ready":
            raise ValueError(f"record {index} source is not ready in the snapshot")
        if (source_manifest.get("revision_policy") == "exclude_revised"
                and source_manifest.get("revised_observation_count", 0) > 0):
            raise ValueError("snapshot excluded revised bars but does not preserve the exclusion key list")
        partitions = source_manifest.get("partitions", {})
        holdout = partitions.get("holdout")
        if not holdout:
            raise ValueError(f"record {index} source has no holdout partition")
        origin = _instant(record.get("origin_timestamp"), "origin_timestamp")
        target = _instant(record.get("target_timestamp"), "target_timestamp")
        forecast_created = _instant(record.get("forecast_created_at"), "forecast_created_at")
        if forecast_created > origin:
            raise ValueError(f"record {index} forecast_created_at is after origin_timestamp")
        if target <= origin:
            raise ValueError(f"record {index} target_timestamp must be after origin_timestamp")
        holdout_start = _instant(holdout["first_timestamp_utc"], "holdout start")
        holdout_end = _instant(holdout["last_timestamp_utc"], "holdout end")
        if not holdout_start <= origin <= holdout_end:
            raise ValueError(f"record {index} origin_timestamp is outside the source holdout partition")
        if not holdout_start <= target <= holdout_end:
            raise ValueError(f"record {index} target_timestamp is outside the source holdout partition")
        bars = by_source.get(source, {})
        if origin not in bars:
            raise ValueError(f"record {index} origin_timestamp is not present in the snapshot source")
        if target not in bars:
            raise ValueError(f"record {index} target_timestamp is not present in the snapshot source")
        actual_return = bars[target] / bars[origin] - 1.0
        if not math.isfinite(actual_return):
            raise ValueError(f"record {index} realized return is outside the finite numeric range")
        evaluated = dict(record)
        evaluated["actual_return"] = actual_return
        evaluated_records.append(evaluated)

    result = evaluate_heldout_forecasts(evaluated_records)
    result["mode"] = "snapshot_backed_holdout_forecast_evaluation"
    result["snapshot"] = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "manifest_sha256": snapshot.get("manifest_sha256"),
        "dataset_sha256": snapshot.get("dataset_sha256"),
        "symbol": snapshot.get("symbol"),
        "interval": snapshot.get("interval"),
    }
    result["actual_return_method"] = "close_to_close_simple_return_from_verified_snapshot_bars"
    result["limitations"] = [
        "Forecasts and their creation timestamps remain caller-supplied and are not independently authenticated.",
        "Realized returns are computed from the captured snapshot OHLCV close values, not supplied actual_return fields.",
        "The evaluator checks that targets lie within each source's chronological holdout range; it does not validate the forecasting model or establish future performance.",
        "The zero-return baseline is descriptive, not a trading strategy or investment recommendation.",
        "No forecasts are generated and no orders are placed.",
    ]
    return result
