"""Reusable, non-mutating validation report for market-data batch payloads.

This module reports structural contract failures; it does not authenticate providers,
certify licensing, or infer missing market sessions.
"""
from typing import Any

from pydantic import ValidationError

from app.market_data import MarketDataBatch


def validate_market_data_payload(payload: Any) -> dict[str, Any]:
    """Validate a payload and return a compact JSON-serializable report.

    The original payload is never modified. Invalid payloads return field-level
    validation messages instead of raising, making this suitable for UI/API review.
    """
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
            "valid": False,
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

    timestamps = [bar.timestamp for bar in batch.bars]
    return {
        "valid": True,
        "bar_count": len(batch.bars),
        "symbol": batch.symbol,
        "interval": batch.interval,
        "source": batch.source,
        "status": batch.status.value,
        "timestamp_start": timestamps[0].isoformat() if timestamps else None,
        "timestamp_end": timestamps[-1].isoformat() if timestamps else None,
        "errors": [],
        "warnings": list(batch.warnings),
        "limitations": [
            "Validation does not authenticate the provider or verify licensing.",
            "Validation does not establish market-session completeness or data freshness.",
        ],
    }
