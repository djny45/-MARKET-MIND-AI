"""Cross-source historical OHLCV comparison; preserves original observations."""
from datetime import datetime, timezone

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
            values = [float(item[field]) for items in by_source.values()
                      for item in items if item.get(field) is not None]
            ranges[field] = {
                "minimum": min(values) if values else None,
                "maximum": max(values) if values else None,
                "absolute_spread": max(values) - min(values) if values else None,
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
        "source_count": len({str(bar.get("source") or "unknown") for bar in bars}),
        "shared_timestamp_count": len(comparisons),
        "comparisons": comparisons,
        "invalid_timestamp_count": len(invalid),
        "invalid_timestamps": invalid,
        "methodology": [
            "Only timezone-aware timestamps representing the exact same UTC instant are compared.",
            "Original timestamp strings, source labels, statuses and retrieval times are retained.",
            "Field ranges describe disagreement; no source is ranked, selected or overwritten.",
            "No missing values, prices or bars are inferred.",
        ],
    }
