"""Leakage-checked evaluation of caller-supplied, held-out return forecasts.

This module scores forecasts for research validation only. It does not generate
forecasts, recommend trades, or execute orders.
"""
from datetime import datetime, timezone
import math


def _instant(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _finite(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def evaluate_heldout_forecasts(records):
    """Evaluate forecasts only when they were recorded by origin and target is later."""
    if not isinstance(records, list) or not 3 <= len(records) <= 10000:
        raise ValueError("records must contain between 3 and 10000 holdout observations")

    parsed = []
    seen = set()
    source_refs = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} must be an object")
        if record.get("partition") != "holdout":
            raise ValueError(f"record {index} must belong to the holdout partition")
        created = _instant(record.get("forecast_created_at"), "forecast_created_at")
        origin = _instant(record.get("origin_timestamp"), "origin_timestamp")
        target = _instant(record.get("target_timestamp"), "target_timestamp")
        if created > origin:
            raise ValueError(f"record {index} forecast_created_at is after origin_timestamp")
        if target <= origin:
            raise ValueError(f"record {index} target_timestamp must be after origin_timestamp")
        key = (origin, target)
        if key in seen:
            raise ValueError(f"record {index} duplicates an origin/target pair")
        seen.add(key)
        predicted = _finite(record.get("predicted_return"), "predicted_return")
        actual = _finite(record.get("actual_return"), "actual_return")
        refs = record.get("source_refs")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError(f"record {index} requires non-empty source_refs")
        source_refs.update(ref.strip() for ref in refs)
        parsed.append((target, predicted, actual))

    parsed.sort(key=lambda item: item[0])
    errors = [predicted - actual for _, predicted, actual in parsed]
    absolute_errors = [abs(error) for error in errors]
    squared_errors = [error * error for error in errors]
    actuals = [actual for _, _, actual in parsed]
    predictions = [predicted for _, predicted, _ in parsed]
    directional = [
        (predicted, actual) for predicted, actual in zip(predictions, actuals)
        if predicted != 0 and actual != 0
    ]
    zero_baseline_mae = sum(abs(value) for value in actuals) / len(actuals)
    mae = sum(absolute_errors) / len(absolute_errors)
    rmse = math.sqrt(sum(squared_errors) / len(squared_errors))
    directional_accuracy = (
        sum((predicted > 0) == (actual > 0) for predicted, actual in directional) / len(directional)
        if directional else None
    )
    skill = 1.0 - mae / zero_baseline_mae if zero_baseline_mae else None

    return {
        "mode": "heldout_forecast_error_evaluation",
        "partition": "holdout",
        "observation_count": len(parsed),
        "target_time_range_utc": {
            "first": parsed[0][0].isoformat(),
            "last": parsed[-1][0].isoformat(),
        },
        "source_reference_count": len(source_refs),
        "metrics": {
            "mae": mae,
            "rmse": rmse,
            "mean_error_bias": sum(errors) / len(errors),
            "zero_return_baseline_mae": zero_baseline_mae,
            "mae_skill_vs_zero_return_baseline": skill,
            "directional_accuracy": directional_accuracy,
            "directional_observation_count": len(directional),
        },
        "leakage_checks": {
            "all_forecasts_created_at_or_before_origin": True,
            "all_targets_after_origin": True,
            "duplicate_origin_target_pairs": 0,
            "non_holdout_records": 0,
        },
        "limitations": [
            "Forecasts and realized returns are caller-supplied; timestamps and source references are not independently authenticated.",
            "The zero-return baseline is a descriptive comparator, not a trading strategy or investment recommendation.",
            "Metrics describe this supplied holdout sample only and do not establish future performance or statistical significance.",
            "No forecasts are generated, no orders are placed, and no capital allocation is recommended.",
        ],
        "research_only": True,
    }
