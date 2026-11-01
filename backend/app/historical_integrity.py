"""Per-source historical OHLCV integrity matrix; no opaque composite score."""
from datetime import datetime, timezone
import math

NUMERIC_FIELDS = ("open", "high", "low", "close", "volume")


def _utc_instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def build_historical_integrity_matrix(history):
    """Summarize timestamp, field and OHLCV structural integrity by source."""
    bars = history.get("bars", [])
    sources = {}
    all_instants = {}
    invalid_timestamp_count = 0

    for index, bar in enumerate(bars):
        source = str(bar.get("source") or "unknown")
        record = sources.setdefault(source, {
            "observation_count": 0,
            "valid_timestamp_count": 0,
            "invalid_timestamp_count": 0,
            "unique_utc_timestamp_count": 0,
            "duplicate_utc_timestamp_count": 0,
            "missing_field_counts": {field: 0 for field in NUMERIC_FIELDS},
            "invalid_numeric_field_counts": {field: 0 for field in NUMERIC_FIELDS},
            "valid_numeric_field_counts": {field: 0 for field in NUMERIC_FIELDS},
            "invalid_ohlcv_structure_count": 0,
            "invalid_ohlcv_examples": [],
            "_instants": set(),
        })
        record["observation_count"] += 1
        instant = _utc_instant(bar.get("timestamp"))
        if instant is None:
            record["invalid_timestamp_count"] += 1
            invalid_timestamp_count += 1
        else:
            record["valid_timestamp_count"] += 1
            if instant in record["_instants"]:
                record["duplicate_utc_timestamp_count"] += 1
            else:
                record["_instants"].add(instant)
            all_instants.setdefault(instant, set()).add(source)

        values = {}
        for field in NUMERIC_FIELDS:
            if field not in bar or bar.get(field) is None:
                record["missing_field_counts"][field] += 1
                continue
            numeric = _number(bar.get(field))
            if numeric is None:
                record["invalid_numeric_field_counts"][field] += 1
            else:
                record["valid_numeric_field_counts"][field] += 1
                values[field] = numeric

        if len(values) == len(NUMERIC_FIELDS):
            structurally_valid = (
                values["open"] > 0 and values["high"] > 0
                and values["low"] > 0 and values["close"] > 0
                and values["volume"] >= 0
                and values["high"] >= max(values["open"], values["close"])
                and values["low"] <= min(values["open"], values["close"])
                and values["high"] >= values["low"]
            )
            if not structurally_valid:
                record["invalid_ohlcv_structure_count"] += 1
                if len(record["invalid_ohlcv_examples"]) < 10:
                    record["invalid_ohlcv_examples"].append({
                        "bar_index": index,
                        "timestamp": bar.get("timestamp"),
                        "reason": "OHLC bounds, positive price or non-negative volume constraint failed",
                    })

    for record in sources.values():
        record["unique_utc_timestamp_count"] = len(record.pop("_instants"))

    shared_instants = [instant for instant, labels in all_instants.items() if len(labels) > 1]
    source_reports = {}
    for source, record in sorted(sources.items()):
        source_reports[source] = {
            **record,
            "timestamp_coverage_pct": round(
                100 * record["valid_timestamp_count"] / record["observation_count"], 3
            ) if record["observation_count"] else None,
            "ohlcv_structure_valid_count": (
                record["observation_count"] - record["invalid_ohlcv_structure_count"]
                - sum(record["missing_field_counts"].values())
                - sum(record["invalid_numeric_field_counts"].values())
            ),
        }

    return {
        "mode": "descriptive_historical_integrity",
        "symbol": history.get("symbol"),
        "interval": history.get("interval"),
        "observation_count": len(bars),
        "source_count": len(source_reports),
        "invalid_timestamp_count": invalid_timestamp_count,
        "shared_utc_timestamp_count": len(shared_instants),
        "sources": source_reports,
        "methodology": [
            "Timestamp duplicates are detected per source after conversion to timezone-aware UTC instants.",
            "Numeric fields are checked for missing, malformed and non-finite values separately.",
            "OHLC structure requires positive prices, high at least open and close, low at most open and close, high at least low, and non-negative volume.",
            "No composite quality score is assigned; dimensions remain separately inspectable.",
            "This report does not authenticate providers, establish licensing or freshness, or select a preferred source.",
        ],
    }
