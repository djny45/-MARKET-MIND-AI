"""Cross-provider indicator comparison at exact shared UTC timestamps."""
import math
from datetime import datetime, timezone

from . import indicators

INDICATORS = (
    "sma_20", "ema_20", "rsi_14", "macd", "macd_signal",
    "bollinger_upper_20", "bollinger_middle_20", "bollinger_lower_20",
)


def _instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _finite_close(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def compare_source_indicator_series(history, revisioned_keys=None, revision_policy="annotate"):
    """Compute independent source indicators with an explicit revision policy."""
    if not isinstance(revision_policy, str) or revision_policy not in {"annotate", "exclude_revised", "block_revised"}:
        raise ValueError("revision_policy must be annotate, exclude_revised, or block_revised")
    revised = {
        (str(item.get("source") or "unknown"), str(item.get("timestamp")))
        for item in (revisioned_keys or [])
        if isinstance(item, dict) and item.get("timestamp") is not None
    }
    groups = {}
    for index, bar in enumerate(history.get("bars", [])):
        source = str(bar.get("source") or "unknown")
        groups.setdefault(source, []).append((index, bar))

    source_values = {}
    source_reports = {}
    for source, indexed_bars in sorted(groups.items()):
        revised_bars = [
            (index, bar) for index, bar in indexed_bars
            if (source, str(bar.get("timestamp"))) in revised
        ]
        revision_info = {
            "revision_policy": revision_policy,
            "revised_observation_count": len(revised_bars),
            "revision_review_required": bool(revised_bars) and revision_policy == "annotate",
            "excluded_revised_observation_count": (
                len(revised_bars) if revision_policy == "exclude_revised" else 0
            ),
        }
        if revised_bars and revision_policy == "block_revised":
            source_reports[source] = {
                "status": "blocked_revised_observations",
                "observation_count": len(indexed_bars),
                "indicator_values_compared": False,
                **revision_info,
            }
            continue
        if revision_policy == "exclude_revised":
            indexed_bars = [
                (index, bar) for index, bar in indexed_bars
                if (source, str(bar.get("timestamp"))) not in revised
            ]
        parsed = []
        invalid = []
        seen = set()
        duplicates = []
        for index, bar in indexed_bars:
            instant = _instant(bar.get("timestamp"))
            close = _finite_close(bar.get("close"))
            if instant is None or close is None:
                invalid.append({
                    "bar_index": index,
                    "timestamp": bar.get("timestamp"),
                    "reason": "invalid_timezone_aware_timestamp" if instant is None else "close_must_be_finite_and_positive",
                })
                continue
            if instant in seen:
                duplicates.append({"bar_index": index, "timestamp_utc": instant.isoformat()})
            seen.add(instant)
            parsed.append((instant, close, index, bar.get("timestamp")))

        if duplicates:
            source_reports[source] = {
                "status": "blocked_duplicate_instants",
                "observation_count": len(indexed_bars),
                "duplicate_count": len(duplicates),
                "duplicates": duplicates[:20],
                "invalid_observation_count": len(invalid),
                "invalid_observations": invalid[:20],
                "indicator_values_compared": False,
                **revision_info,
            }
            continue
        if invalid:
            source_reports[source] = {
                "status": "blocked_invalid_observations",
                "observation_count": len(indexed_bars),
                "invalid_observation_count": len(invalid),
                "invalid_observations": invalid[:20],
                "indicator_values_compared": False,
                **revision_info,
            }
            continue
        if len(parsed) < 2:
            source_reports[source] = {
                "status": "insufficient_source_history",
                "observation_count": len(indexed_bars),
                "indicator_values_compared": False,
                **revision_info,
            }
            continue

        parsed.sort(key=lambda item: item[0])
        closes = [item[1] for item in parsed]
        sma = indicators.sma(closes, 20)
        ema = indicators.ema(closes, 20)
        rsi = indicators.rsi(closes, 14)
        macd = indicators.macd(closes, 12, 26, 9)
        bands = indicators.bollinger(closes, 20)
        values_by_instant = {}
        for index, (instant, _, original_index, timestamp) in enumerate(parsed):
            values_by_instant[instant] = {
                "timestamp": timestamp,
                "bar_index": original_index,
                "sma_20": sma[index],
                "ema_20": ema[index],
                "rsi_14": rsi[index - 1] if index > 0 else None,
                "macd": macd["macd"][index],
                "macd_signal": macd["signal"][index],
                "bollinger_upper_20": bands["upper"][index],
                "bollinger_middle_20": bands["middle"][index],
                "bollinger_lower_20": bands["lower"][index],
            }
        source_values[source] = values_by_instant
        source_reports[source] = {
            "status": "evaluated",
            "observation_count": len(indexed_bars),
            "valid_observation_count": len(parsed),
            "indicator_values_compared": True,
            "parameters": {"sma": 20, "ema": 20, "rsi": 14, "macd": [12, 26, 9], "bollinger": 20},
            **revision_info,
        }

    shared = {}
    for source, values in source_values.items():
        for instant, value in values.items():
            shared.setdefault(instant, {})[source] = value

    comparisons = []
    for instant, values in sorted(shared.items()):
        if len(values) < 2:
            continue
        field_ranges = {}
        for field in INDICATORS:
            numeric = [
                item[field] for item in values.values()
                if item[field] is not None and math.isfinite(item[field])
            ]
            field_ranges[field] = {
                "minimum": min(numeric) if numeric else None,
                "maximum": max(numeric) if numeric else None,
                "absolute_spread": max(numeric) - min(numeric) if numeric else None,
                "valid_source_count": len(numeric),
            }
        comparisons.append({
            "timestamp_utc": instant.isoformat(),
            "sources": {
                source: {"bar_index": item["bar_index"], "indicator_values": {
                    field: item[field] for field in INDICATORS
                }}
                for source, item in sorted(values.items())
            },
            "field_ranges": field_ranges,
        })

    return {
        "mode": "source_isolated_indicator_comparison",
        "symbol": history.get("symbol"),
        "interval": history.get("interval"),
        "source_count": len(groups),
        "evaluated_source_count": len(source_values),
        "shared_timestamp_count": len(comparisons),
        "comparison_count": len(comparisons) * len(INDICATORS),
        "source_reports": source_reports,
        "comparisons": comparisons,
        "methodology": [
            "Each source receives an independent chronological indicator calculation; provider bars are never interleaved.",
            "Only exact matching timezone-aware UTC instants are compared.",
            "Sources with invalid observations or duplicate UTC instants are blocked rather than silently repaired or deduplicated.",
            "Revision policy is explicit: annotate flags revised current observations, exclude_revised removes them before calculation, and block_revised blocks affected sources.",
            "All providers use fixed SMA-20, EMA-20, RSI-14, MACD(12,26,9) and Bollinger-20 parameters.",
            "Indicator disagreement is descriptive; no provider is ranked or selected and no price series is treated as authoritative.",
            "This does not establish formula correctness, provider authenticity, data licensing or predictive accuracy.",
        ],
        "research_only": True,
    }
