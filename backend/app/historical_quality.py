"""Robust historical observation diagnostics; no inferred prices or trade signals."""
from datetime import datetime
import math

INTERVAL_SECONDS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] / 2) + (ordered[middle] / 2)


def _mad_flags(values, minimum=20, threshold=6.0):
    if len(values) < minimum:
        return {"status": "insufficient_history", "sample_count": len(values), "threshold_mad": threshold, "flagged_indices": []}
    center = _median(values)
    mad = _median([abs(value - center) for value in values])
    if mad is None or mad == 0:
        return {"status": "unavailable_zero_mad", "sample_count": len(values), "median": center, "mad": mad, "threshold_mad": threshold, "flagged_indices": []}
    flags = [i for i, value in enumerate(values) if abs(value - center) / (1.4826 * mad) > threshold]
    return {"status": "available", "sample_count": len(values), "median": center, "mad": mad, "threshold_mad": threshold, "flagged_indices": flags}


def build_historical_quality_diagnostics(history):
    bars = history.get("bars", [])
    interval = history.get("interval")
    expected = INTERVAL_SECONDS.get(interval)
    parsed = [_timestamp(bar.get("timestamp")) for bar in bars]
    valid_pairs = [(i, value) for i, value in enumerate(parsed) if value is not None]
    invalid_timestamps = [{"bar_index": i, "timestamp": bars[i].get("timestamp")}
                          for i, value in enumerate(parsed) if value is None]
    seen_timestamps = {}
    duplicate_timestamps = []
    for i, value in valid_pairs:
        if value in seen_timestamps:
            duplicate_timestamps.append({"bar_index": i, "first_bar_index": seen_timestamps[value],
                                          "timestamp": bars[i].get("timestamp")})
        else:
            seen_timestamps[value] = i
    out_of_order_timestamps = []
    for (previous_index, previous), (current_index, current) in zip(valid_pairs, valid_pairs[1:]):
        if current < previous:
            out_of_order_timestamps.append({"bar_index": current_index, "previous_bar_index": previous_index,
                                            "timestamp": bars[current_index].get("timestamp"),
                                            "previous_timestamp": bars[previous_index].get("timestamp")})
    spacing = []
    if expected:
        for (previous_index, previous), (current_index, current) in zip(valid_pairs, valid_pairs[1:]):
            delta = current - previous
            if delta > expected * 1.5:
                spacing.append({"from_index": previous_index, "to_index": current_index,
                                "elapsed_seconds": delta, "expected_interval_seconds": expected,
                                "from_timestamp": bars[previous_index].get("timestamp"),
                                "to_timestamp": bars[current_index].get("timestamp"),
                                "interval_multiples": round(delta / expected, 3)})
    returns = []
    return_indices = []
    for i in range(1, len(bars)):
        try:
            previous, current = float(bars[i - 1]["close"]), float(bars[i]["close"])
            if math.isfinite(previous) and math.isfinite(current) and previous > 0 and current > 0:
                value = (current / previous) - 1
                if math.isfinite(value):
                    returns.append(value)
                    return_indices.append(i)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    price_result = _mad_flags(returns)
    price_result["flagged_bar_indices"] = [return_indices[i] for i in price_result["flagged_indices"]]
    price_result["flagged_observations"] = [{
        "bar_index": return_indices[i],
        "timestamp": bars[return_indices[i]].get("timestamp"),
        "previous_timestamp": bars[return_indices[i] - 1].get("timestamp"),
        "previous_close": float(bars[return_indices[i] - 1]["close"]),
        "close": float(bars[return_indices[i]]["close"]),
        "return_pct": round(returns[i] * 100, 6),
        "robust_deviation_mad": round(abs(returns[i] - price_result["median"]) / (1.4826 * price_result["mad"]), 3)
    } for i in price_result["flagged_indices"]] if price_result["status"] == "available" else []
    volumes = []
    volume_indices = []
    for i, bar in enumerate(bars):
        try:
            value = float(bar["volume"])
            if math.isfinite(value) and value >= 0:
                volumes.append(value)
                volume_indices.append(i)
        except (KeyError, TypeError, ValueError):
            continue
    volume_result = _mad_flags(volumes)
    volume_result["flagged_bar_indices"] = [volume_indices[i] for i in volume_result["flagged_indices"]]
    volume_result["flagged_observations"] = [{
        "bar_index": volume_indices[i],
        "timestamp": bars[volume_indices[i]].get("timestamp"),
        "volume": volumes[i],
        "robust_deviation_mad": round(abs(volumes[i] - volume_result["median"]) / (1.4826 * volume_result["mad"]), 3)
    } for i in volume_result["flagged_indices"]] if volume_result["status"] == "available" else []
    return {
        "interval": interval,
        "bars_checked": len(bars),
        "timestamp_integrity": {
            "invalid_timestamp_count": len(invalid_timestamps),
            "invalid_timestamps": invalid_timestamps,
            "duplicate_timestamp_count": len(duplicate_timestamps),
            "duplicate_timestamps": duplicate_timestamps,
            "out_of_order_count": len(out_of_order_timestamps),
            "out_of_order_timestamps": out_of_order_timestamps,
            "interpretation": "Checks compare parsed timezone-aware instants; input bars are not reordered or repaired.",
        },
        "timestamp_spacing": {
            "status": "available" if expected else "unsupported_interval",
            "expected_interval_seconds": expected,
            "spacing_anomaly_count": len(spacing),
            "spacing_anomalies": spacing,
            "interpretation": "Elapsed-time gaps only; exchange sessions, holidays and provider schedules are not modelled.",
        },
        "close_to_close_return_outliers": price_result,
        "volume_outliers": volume_result,
        "methodology": [
            "Outliers use a robust median/MAD screen with a 6-MAD threshold and at least 20 observations.",
            "Zero-MAD samples are reported as unavailable rather than assigned a fabricated threshold.",
            "Indices refer to the supplied chronological bar sequence; no missing prices or bars are generated.",
            "Flags are statistical review prompts, not evidence of bad data or trading signals.",
        ],
    }
