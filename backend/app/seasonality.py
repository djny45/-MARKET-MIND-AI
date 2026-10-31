"""Descriptive calendar-bucket summaries of historical close-to-close returns."""
import math
from collections import defaultdict
from datetime import datetime
from statistics import median
from calendar import day_name, month_name


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def build_seasonality_report(bars):
    """Group valid consecutive close returns by weekday and calendar month."""
    weekdays = defaultdict(list)
    months = defaultdict(list)
    skipped = 0
    ordered = []
    for index, bar in enumerate(bars):
        try:
            stamp = datetime.fromisoformat(str(bar.get("timestamp", "")).replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("timezone_required")
            close = _number(bar.get("close"))
            if close is None or close <= 0:
                raise ValueError("invalid_close")
            ordered.append((stamp, close, index))
        except (TypeError, ValueError):
            skipped += 1
    ordered.sort(key=lambda item: item[0])
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] <= previous[0]:
            skipped += 1
            continue
        change = (current[1] / previous[1] - 1.0) * 100.0
        if not math.isfinite(change):
            skipped += 1
            continue
        weekdays[current[0].weekday()].append(change)
        months[current[0].month].append(change)

    def summarize(groups, labels):
        result = []
        for key in sorted(groups):
            values = groups[key]
            result.append({
                "bucket": labels[key],
                "sample_count": len(values),
                "mean_return_pct": round(sum(values) / len(values), 6),
                "median_return_pct": round(median(values), 6),
                "positive_count": sum(value > 0 for value in values),
                "negative_count": sum(value < 0 for value in values),
                "unchanged_count": sum(value == 0 for value in values),
            })
        return result

    weekday_labels = {index: day_name[index] for index in range(7)}
    month_labels = {index: month_name[index] for index in range(1, 13)}
    return {
        "status": "available" if sum(len(values) for values in weekdays.values()) else "insufficient_valid_observations",
        "valid_close_observations": len(ordered),
        "return_observations": sum(len(values) for values in weekdays.values()),
        "skipped_observations": skipped,
        "by_weekday": summarize(weekdays, weekday_labels),
        "by_calendar_month": summarize(months, month_labels),
        "limitations": [
            "Buckets are descriptive summaries of the supplied stored observations only.",
            "No minimum sample threshold, statistical significance, or predictive edge is inferred.",
            "Returns are consecutive available observations; missing bars and exchange sessions are not reconstructed.",
            "Results depend on the supplied interval, date range, timezone, provider coverage, and data quality.",
            "No annualization, forecast, recommendation, or trading signal is produced.",
        ],
    }
