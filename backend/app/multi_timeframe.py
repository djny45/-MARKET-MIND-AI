"""Optional multi-timeframe descriptive research over locally stored bars."""
from .chart_research import build_chart_report

SUPPORTED_INTERVALS = ("15m", "1h", "4h", "1d")


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

    return {
        "mode": "multi_timeframe_descriptive_research",
        "symbol": symbol.strip().upper(),
        "timeframes_requested": list(histories.keys()),
        "timeframes_analyzed": list(reports.keys()),
        "timeframes_missing_or_insufficient": missing,
        "reports": reports,
        "moving_average_structure_by_timeframe": regimes,
        "cross_timeframe_comparison": alignment,
        "warnings": [
            "Timeframes are compared only when stored bars are available.",
            "Different intervals may cover different observation windows; this is not a synchronized signal.",
            "No price data is interpolated or fabricated for missing intervals.",
        ],
        "interpretation": "Optional multi-timeframe comparison of descriptive observations only; not a forecast, recommendation, or trade signal.",
        "execution": "disabled",
    }
