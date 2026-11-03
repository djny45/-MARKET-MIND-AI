"""Chronological split utilities for leakage-aware research evaluation.

This module only validates time-series evaluation boundaries. It does not train
models, generate signals, or connect to trading/execution services.
"""
from datetime import datetime, timezone
from typing import Any


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def validate_chronological_splits(
    train_end: str,
    validation_start: str,
    validation_end: str,
    test_start: str,
    *,
    embargo_seconds: int = 0,
) -> dict[str, Any]:
    """Validate ordered split boundaries and a configurable embargo.

    Boundary timestamps are treated as the last timestamp in each preceding
    split and the first timestamp in the next split. The gaps must be at least
    embargo_seconds. The function validates boundaries only; it cannot inspect
    feature windows or prove that upstream data has no leakage.
    """
    if not isinstance(embargo_seconds, int) or isinstance(embargo_seconds, bool) or embargo_seconds < 0:
        raise ValueError("embargo_seconds must be a non-negative integer")

    train = _parse_timestamp(train_end, "train_end")
    val_start = _parse_timestamp(validation_start, "validation_start")
    val_end = _parse_timestamp(validation_end, "validation_end")
    test = _parse_timestamp(test_start, "test_start")

    # Normalize to UTC for comparisons without relying on local timezone.
    train, val_start, val_end, test = (
        item.astimezone(timezone.utc) for item in (train, val_start, val_end, test)
    )
    embargo = (val_start - train).total_seconds()
    test_embargo = (test - val_end).total_seconds()

    if val_start <= train:
        raise ValueError("validation_start must be after train_end")
    if val_end < val_start:
        raise ValueError("validation_end must be on or after validation_start")
    if test <= val_end:
        raise ValueError("test_start must be after validation_end")
    if embargo < embargo_seconds:
        raise ValueError("train/validation boundary does not satisfy embargo_seconds")
    if test_embargo < embargo_seconds:
        raise ValueError("validation/test boundary does not satisfy embargo_seconds")

    return {
        "valid": True,
        "method": "chronological",
        "timezone_normalized": "UTC",
        "embargo_seconds": embargo_seconds,
        "train_end": train.isoformat(),
        "validation_start": val_start.isoformat(),
        "validation_end": val_end.isoformat(),
        "test_start": test.isoformat(),
        "train_validation_gap_seconds": embargo,
        "validation_test_gap_seconds": test_embargo,
        "random_shuffling_allowed": False,
        "research_only": True,
    }
