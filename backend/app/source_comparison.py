"""Cross-source historical OHLCV comparison; preserves original observations."""
from datetime import datetime, timezone
import math

FIELDS = ("open", "high", "low", "close", "volume")


def _instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def compare_source_observations(history):
    """Compare source observations at identical UTC instants without selecting a winner."""
    bars = history.get("bars", [])
    grouped = {}
    invalid = []
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            invalid.append({
                "bar_index": index,
                "timestamp": None,
                "reason": "observation_must_be_object",
            })
            continue
        instant = _instant(bar.get("timestamp"))
        if instant is None:
            invalid.append({"bar_index": index, "timestamp": bar.get("timestamp")})
            continue
        grouped.setdefault(instant, []).append((index, bar))

    comparisons = []
    for instant in sorted(grouped):
        observations = grouped[instant]
        by_source = {}
        for index, bar in observations:
            by_source.setdefault(str(bar.get("source") or "unknown"), []).append({
                "bar_index": index,
                "timestamp": bar.get("timestamp"),
                "status": bar.get("status"),
                "retrieved_at": bar.get("retrieved_at"),
                **{field: bar.get(field) for field in FIELDS},
            })
        if len(by_source) < 2:
            continue
        ranges = {}
        for field in FIELDS:
            values = []
            invalid_values = []
            missing_count = 0
            for source, items in by_source.items():
                for item in items:
                    raw = item.get(field)
                    if raw is None:
                        missing_count += 1
                        continue
                    try:
                        numeric = float(raw)
                        if not math.isfinite(numeric):
                            raise ValueError("non-finite numeric value")
                        values.append(numeric)
                    except (TypeError, ValueError, OverflowError):
                        invalid_values.append({
                            "source": source,
                            "bar_index": item["bar_index"],
                            "raw_value": raw,
                        })
            minimum = min(values) if values else None
            maximum = max(values) if values else None
            spread = maximum - minimum if values else None
            spread_status = "available"
            if spread is not None and not math.isfinite(spread):
                spread = None
                spread_status = "unavailable_nonfinite_spread"
            ranges[field] = {
                "minimum": minimum,
                "maximum": maximum,
                "absolute_spread": spread,
                "spread_status": spread_status if values else "no_valid_values",
                "valid_value_count": len(values),
                "missing_value_count": missing_count,
                "invalid_value_count": len(invalid_values),
                "invalid_values": invalid_values,
            }
        comparisons.append({
            "timestamp_utc": instant.isoformat(),
            "source_count": len(by_source),
            "sources": by_source,
            "field_ranges": ranges,
            "same_source_duplicate_count": sum(max(0, len(items) - 1) for items in by_source.values()),
        })

    return {
        "symbol": history.get("symbol"),
        "interval": history.get("interval"),
        "observations_checked": len(bars),
        "source_count": len({str(bar.get("source") or "unknown") for bar in bars if isinstance(bar, dict)}),
        "shared_timestamp_count": len(comparisons),
        "comparisons": comparisons,
        "invalid_timestamp_count": len(invalid),
        "invalid_timestamps": invalid,
        "methodology": [
            "Only timezone-aware timestamps representing the exact same UTC instant are compared.",
            "Original timestamp strings, source labels, statuses and retrieval times are retained.",
            "Field ranges describe disagreement; no source is ranked, selected or overwritten.",
            "Missing, malformed and non-finite numeric fields are counted separately and excluded from ranges.",
            "No missing values, prices or bars are inferred.",
        ],
    }
