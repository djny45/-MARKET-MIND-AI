"""Optional multi-timeframe descriptive research over locally stored bars."""
from .chart_research import build_chart_report
from . import indicators

def _is_iso_timestamp(value: str) -> bool:
    from datetime import datetime
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


SUPPORTED_INTERVALS = ("15m", "1h", "4h", "1d")


def _aligned_indicator_context(histories: dict[str, dict], intervals: list[str]) -> dict:
    """Compare indicator observations only at exact shared bar timestamps."""
    if len(intervals) < 2:
        return {"method": "exact_timestamp_intersection_no_interpolation",
                "common_timestamp_count": 0, "latest_common_timestamp": None,
                "latest_common_observation": None, "status": "insufficient_timeframes",
                "note": "At least two analyzed timeframes are required for cross-timeframe comparison."}
    timestamp_maps = {}
    contexts = {}
    for interval in intervals:
        bars = histories[interval].get("bars", [])
        closes = [float(bar["close"]) for bar in bars]
        sma20 = indicators.sma(closes, 20)
        rsi14 = indicators.rsi(closes, 14)
        macd = indicators.macd(closes)
        by_timestamp = {}
        for index, bar in enumerate(bars):
            timestamp = bar.get("timestamp")
            if not timestamp:
                continue
            by_timestamp[str(timestamp)] = {
                "bar_index": index,
                "close": closes[index],
                "sma20": round(sma20[index], 8) if index >= 19 else None,
                "rsi14": round(rsi14[index - 1], 4) if index > 0 and rsi14[index - 1] is not None else None,
                "macd": round(macd["macd"][index], 8),
                "macd_signal": round(macd["signal"][index], 8),
                "macd_histogram": round(macd["histogram"][index], 8),
            }
        timestamp_maps[interval] = by_timestamp
    if not timestamp_maps:
        return {"method": "exact_timestamp_intersection_no_interpolation",
                "common_timestamp_count": 0, "latest_common_timestamp": None,
                "latest_common_observation": None, "status": "insufficient_data"}
    common = set.intersection(*(set(values) for values in timestamp_maps.values()))
    from datetime import datetime
    ordered = sorted(common, key=lambda value: (0, datetime.fromisoformat(value.replace('Z', '+00:00'))) if _is_iso_timestamp(value) else (1, value))
    if not ordered:
        return {"method": "exact_timestamp_intersection_no_interpolation",
                "common_timestamp_count": 0, "latest_common_timestamp": None,
                "latest_common_observation": None, "status": "no_exact_timestamp_overlap",
                "note": "No exact shared timestamps; no values were interpolated or forward-filled."}
    latest = ordered[-1]
    snapshot = {interval: timestamp_maps[interval][latest] for interval in intervals}
    return {
        "method": "exact_timestamp_intersection_no_interpolation",
        "common_timestamp_count": len(ordered),
        "latest_common_timestamp": latest,
        "latest_common_observation": snapshot,
        "status": "available",
        "note": "Only exact shared timestamps are compared. Indicator values are calculated independently within each timeframe.",
    }


def build_multi_timeframe_report(symbol: str, histories: dict[str, dict]) -> dict:
    if not symbol.strip():
        raise ValueError("symbol is required")
    if not histories:
        raise ValueError("at least one timeframe must be requested")
    unknown = sorted(set(histories) - set(SUPPORTED_INTERVALS))
    if unknown:
        raise ValueError(f"unsupported intervals: {', '.join(unknown)}")

    reports = {}
    missing = []
    for interval in SUPPORTED_INTERVALS:
        if interval not in histories:
            continue
        history = histories[interval]
        if len(history.get("bars", [])) < 2:
            missing.append(interval)
            continue
        reports[interval] = build_chart_report(history)

    regimes = {
        interval: report["observed_structure"]["moving_average_regime"]
        for interval, report in reports.items()
    }
    distinct = set(regimes.values())
    if not regimes:
        alignment = "insufficient_data"
    elif len(distinct) == 1:
        alignment = "same_descriptive_structure_across_available_timeframes"
    else:
        alignment = "mixed_descriptive_structure_across_timeframes"

    aligned_context = _aligned_indicator_context(histories, list(reports.keys())) if reports else {
        "method": "exact_timestamp_intersection_no_interpolation",
        "common_timestamp_count": 0, "latest_common_timestamp": None,
        "latest_common_observation": None, "status": "insufficient_data",
    }
    return {
        "mode": "multi_timeframe_descriptive_research",
        "symbol": symbol.strip().upper(),
        "timeframes_requested": list(histories.keys()),
        "timeframes_analyzed": list(reports.keys()),
        "timeframes_missing_or_insufficient": missing,
        "reports": reports,
        "moving_average_structure_by_timeframe": regimes,
        "cross_timeframe_comparison": alignment,
        "aligned_indicator_comparison": aligned_context,
        "warnings": [
            "Timeframes are compared only when stored bars are available.",
            "Different intervals may cover different observation windows; this is not a synchronized signal.",
            "Indicator comparisons require exact shared timestamps; missing timestamps are not interpolated or forward-filled.",
            "No price data is interpolated or fabricated for missing intervals.",
        ],
        "interpretation": "Optional multi-timeframe comparison of descriptive observations only; not a forecast, recommendation, or trade signal.",
        "execution": "disabled",
    }
