"""Descriptive pairwise cross-market return correlation on aligned historical bars."""
from datetime import datetime, timezone
import math


def _utc_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("bar timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("bar timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("bar timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _close_map(history):
    if not isinstance(history, dict) or not isinstance(history.get("bars"), list):
        raise ValueError("each history must contain a bars array")
    values = {}
    sources, statuses = set(), set()
    for bar in history["bars"]:
        if not isinstance(bar, dict):
            continue
        stamp = _utc_timestamp(bar.get("timestamp"))
        close = bar.get("close")
        if isinstance(close, bool):
            raise ValueError("bar close must be a positive finite number")
        try:
            close = float(close)
        except (TypeError, ValueError) as exc:
            raise ValueError("bar close must be a positive finite number") from exc
        if not math.isfinite(close) or close <= 0:
            raise ValueError("bar close must be a positive finite number")
        key = stamp.isoformat()
        if key in values:
            raise ValueError("duplicate UTC timestamps prevent unambiguous alignment")
        values[key] = close
        if bar.get("source"):
            sources.add(str(bar["source"]))
        if bar.get("status"):
            statuses.add(str(bar["status"]))
    return values, sorted(sources), sorted(statuses)


def _pearson(left, right):
    n = len(left)
    mean_left, mean_right = sum(left) / n, sum(right) / n
    covariance = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    variance_left = sum((x - mean_left) ** 2 for x in left)
    variance_right = sum((y - mean_right) ** 2 for y in right)
    denominator = math.sqrt(variance_left * variance_right)
    if denominator == 0:
        return None
    return covariance / denominator


def build_cross_market_correlation(histories, interval, min_observations=20):
    """Calculate pairwise Pearson correlation of close-to-close simple returns."""
    if not isinstance(histories, dict) or not 2 <= len(histories) <= 12:
        raise ValueError("histories must contain between 2 and 12 instruments")
    if not isinstance(interval, str) or not interval.strip():
        raise ValueError("interval is required")
    if isinstance(min_observations, bool) or not isinstance(min_observations, int) or not 3 <= min_observations <= 5000:
        raise ValueError("min_observations must be between 3 and 5000")
    series = {}
    metadata = {}
    for instrument, history in sorted(histories.items()):
        if not isinstance(instrument, str) or not instrument.strip():
            raise ValueError("instrument identifiers must be non-empty strings")
        bars, sources, statuses = _close_map(history)
        series[instrument] = bars
        metadata[instrument] = {
            "bar_count": len(bars), "sources": sources, "statuses": statuses,
            "first_timestamp": min(bars) if bars else None,
            "last_timestamp": max(bars) if bars else None,
        }
    pairs = []
    names = sorted(series)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1:]:
            left, right = series[left_name], series[right_name]
            common = sorted(set(left) & set(right))
            returns_left, returns_right, endpoints = [], [], []
            for previous, current in zip(common, common[1:]):
                left_return = left[current] / left[previous] - 1.0
                right_return = right[current] / right[previous] - 1.0
                returns_left.append(left_return)
                returns_right.append(right_return)
                endpoints.append(current)
            count = len(returns_left)
            coefficient = _pearson(returns_left, returns_right) if count >= min_observations else None
            pairs.append({
                "left_instrument": left_name, "right_instrument": right_name,
                "correlation": round(coefficient, 8) if coefficient is not None else None,
                "return_observations": count,
                "status": "available" if coefficient is not None else "insufficient_overlap",
                "first_return_endpoint": endpoints[0] if endpoints else None,
                "last_return_endpoint": endpoints[-1] if endpoints else None,
                "aligned_bar_count": len(common),
            })
    return {
        "status": "descriptive_historical_correlation",
        "interval": interval,
        "method": "Pearson correlation of simple close-to-close returns over exact shared UTC bar timestamps",
        "minimum_return_observations": min_observations,
        "instruments": metadata,
        "pairs": pairs,
        "alignment": "Only exact UTC timestamp intersections are used; returns are calculated between consecutive shared timestamps. No forward fill or timezone guessing is applied.",
        "limitations": [
            "Correlation is descriptive and does not establish causality, predictive power or future co-movement.",
            "Pairwise samples can differ because instruments have different trading sessions and missing bars.",
            "The interval label is caller-supplied and must represent comparable bar durations.",
            "Sources and statuses are importer-supplied metadata; they are not independently authenticated.",
            "Synthetic and historical observations are identified in per-instrument status metadata and should not be mixed for empirical conclusions."
        ],
        "execution": "disabled",
        "data_note": "Calculated only from locally stored bars; no live feeds, broker connectivity, order routing or trading signals are used."
    }
