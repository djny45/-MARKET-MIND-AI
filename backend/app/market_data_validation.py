"""Reusable, non-mutating validation report for market-data batch payloads.

This module reports structural contract failures; it does not authenticate providers,
certify licensing, or infer missing market sessions.
"""
from datetime import datetime, timezone
import math
from typing import Any

from pydantic import ValidationError

from app.market_data import MarketDataBatch


def validate_market_data_payload(
    payload: Any, *, max_retrieval_age_seconds: int | float | None = None
) -> dict[str, Any]:
    """Validate a payload and return a compact JSON-serializable report.

    The original payload is never modified. Invalid payloads return field-level
    validation messages instead of raising, making this suitable for UI/API review.
    """
    if max_retrieval_age_seconds is not None and (
        isinstance(max_retrieval_age_seconds, bool)
        or not isinstance(max_retrieval_age_seconds, (int, float))
        or not math.isfinite(max_retrieval_age_seconds)
        or max_retrieval_age_seconds < 0
    ):
        raise ValueError("max_retrieval_age_seconds must be a finite non-negative number or None")

    try:
        batch = MarketDataBatch.model_validate(payload)
    except ValidationError as exc:
        errors = [
            {
                "location": ".".join(str(part) for part in item["loc"]),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in exc.errors()
        ]
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "valid": False,
            "result": "invalid",
            "error_count": len(errors),
            "bar_count": None,
            "symbol": None,
            "interval": None,
            "source": None,
            "status": None,
            "errors": errors,
            "warnings": [
                "Structural validation failed; inspect the original payload before analysis."
            ],
            "limitations": [
                "Validation does not authenticate the provider or verify licensing.",
                "Validation does not establish market-session completeness or data freshness.",
            ],
        }

    now = datetime.now(timezone.utc)
    retrieval_age_seconds = max(0.0, (now - batch.retrieved_at).total_seconds())
    retrieval_freshness = None
    warnings = list(batch.warnings)
    if max_retrieval_age_seconds is not None:
        retrieval_freshness = (
            "stale" if retrieval_age_seconds > max_retrieval_age_seconds else "within_threshold"
        )
        if retrieval_freshness == "stale":
            warnings.append(
                "Retrieval metadata exceeds the caller-supplied age threshold; review before analysis."
            )

    timestamps = [bar.timestamp for bar in batch.bars]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieved_at": batch.retrieved_at.isoformat(),
        "retrieval_age_seconds": round(retrieval_age_seconds, 3),
        "retrieval_freshness": retrieval_freshness,
        "freshness_threshold_seconds": max_retrieval_age_seconds,
        "valid": True,
        "result": "valid",
        "error_count": 0,
        "bar_count": len(batch.bars),
        "symbol": batch.symbol,
        "interval": batch.interval,
        "source": batch.source,
        "status": batch.status.value,
        "timestamp_start": timestamps[0].isoformat() if timestamps else None,
        "timestamp_end": timestamps[-1].isoformat() if timestamps else None,
        "errors": [],
        "warnings": warnings,
        "limitations": [
            "Validation does not authenticate the provider or verify licensing.",
            "Validation does not establish market-session completeness or data freshness.",
        ],
    }
