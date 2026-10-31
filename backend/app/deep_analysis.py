"""Integrated, deterministic deep research report over stored OHLCV observations.

This module combines existing chart research with explicit data-quality diagnostics.
It describes observations; it does not forecast, recommend, or execute.
"""
from datetime import datetime
from .market_diagnostics import build_market_diagnostics
from .correlation import build_correlation_report
from .price_levels import build_price_level_clusters
from .market_breadth import build_market_breadth_report
from .research_dashboard import build_research_dashboard
from .seasonality import build_seasonality_report


def _parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def build_data_quality_report(history: dict) -> dict:
    bars = history.get("bars", [])
    timestamps = [bar.get("timestamp") for bar in bars]
    parsed = [_parse_timestamp(value) for value in timestamps]
    duplicate_timestamps = sorted({
        value for value in timestamps if value and timestamps.count(value) > 1
    })
    invalid_timestamps = [i for i, value in enumerate(parsed) if value is None]
    out_of_order = [
        i for i in range(1, len(parsed))
        if parsed[i] is not None and parsed[i - 1] is not None
        and parsed[i] <= parsed[i - 1]
    ]
    invalid_ohlc = []
    negative_volume = []
    missing_fields = []
    required = ("timestamp", "open", "high", "low", "close", "volume")
    for index, bar in enumerate(bars):
        absent = [field for field in required if bar.get(field) is None]
        if absent:
            missing_fields.append({"index": index, "fields": absent})
            continue
        try:
            opening, high = float(bar["open"]), float(bar["high"])
            low, close, volume = float(bar["low"]), float(bar["close"]), float(bar["volume"])
            if min(opening, high, low, close) <= 0 or high < max(opening, close, low) or low > min(opening, close, high):
                invalid_ohlc.append(index)
            if volume < 0:
                negative_volume.append(index)
        except (TypeError, ValueError):
            invalid_ohlc.append(index)

    sources = sorted({str(bar.get("source", "unknown")) for bar in bars})
    statuses = sorted({str(bar.get("status", "unknown")) for bar in bars})
    retrieved = sorted({str(bar.get("retrieved_at")) for bar in bars if bar.get("retrieved_at")})
    issues = (len(duplicate_timestamps) + len(invalid_timestamps) + len(out_of_order)
              + len(invalid_ohlc) + len(negative_volume) + len(missing_fields))
    return {
        "bars_checked": len(bars),
        "quality_status": "issues_detected" if issues else "no_structural_issues_detected",
        "duplicate_timestamps": duplicate_timestamps,
        "invalid_timestamp_indices": invalid_timestamps,
        "non_increasing_timestamp_indices": out_of_order,
        "invalid_ohlc_indices": invalid_ohlc,
        "negative_volume_indices": negative_volume,
        "missing_required_fields": missing_fields,
        "source_counts": {source: sum(1 for bar in bars if str(bar.get("source", "unknown")) == source) for source in sources},
        "status_counts": {status: sum(1 for bar in bars if str(bar.get("status", "unknown")) == status) for status in statuses},
        "retrieval_timestamps": retrieved,
        "limitations": [
            "No freshness verdict is inferred from retrieval timestamps.",
            "No missing-session or missing-bar verdict is inferred because exchange calendars and provider schedules vary.",
            "Structural checks cannot establish that a provider's observations are authentic or licensed.",
        ],
    }


def build_deep_analysis_report(symbol: str, histories: dict, multi_timeframe_report: dict | None = None, correlation_histories: dict | None = None, breadth_histories: dict | None = None) -> dict:
    if not symbol or not symbol.strip():
        raise ValueError("symbol is required")
    if not histories:
        raise ValueError("at least one timeframe history is required")
    timeframe_reports = {}
    for interval, history in histories.items():
        bars = history.get("bars", [])
        try:
            market_diagnostics = build_market_diagnostics(bars)
        except (KeyError, TypeError, ValueError):
            market_diagnostics = {"status": "invalid_data", "limitations": ["Numeric close and volume observations must be valid."]}
        timeframe_reports[interval] = {
            "data_quality": build_data_quality_report(history),
            "market_diagnostics": market_diagnostics,
            "historical_price_clusters": None,
            "chart_research": None,
            "seasonality": build_seasonality_report(bars),
        }
        if len(bars) >= 5:
            try:
                timeframe_reports[interval]["historical_price_clusters"] = build_price_level_clusters(bars)
            except (KeyError, TypeError, ValueError):
                timeframe_reports[interval]["historical_price_clusters"] = {
                    "status": "unavailable_invalid_or_incomplete_data"
                }
        if len(bars) >= 2:
            from .chart_research import build_chart_report
            try:
                timeframe_reports[interval]["chart_research"] = build_chart_report(history)
            except (KeyError, TypeError, ValueError):
                timeframe_reports[interval]["chart_research"] = {
                    "status": "unavailable_invalid_or_incomplete_data",
                    "note": "Chart calculations were skipped; inspect the accompanying data-quality report.",
                }

    result = {
        "mode": "integrated_deep_descriptive_research",
        "symbol": symbol.strip().upper(),
        "timeframes": timeframe_reports,
        "cross_timeframe": multi_timeframe_report,
        "cross_asset_correlation": build_correlation_report(correlation_histories) if correlation_histories else None,
        "market_breadth": build_market_breadth_report(breadth_histories) if breadth_histories else None,
        "coverage": {
            "timeframes_requested": list(histories.keys()),
            "timeframes_with_chart_analysis": [
                key for key, value in timeframe_reports.items() if value["chart_research"] is not None
            ],
            "timeframes_with_insufficient_bars": [
                key for key, value in timeframe_reports.items() if value["chart_research"] is None
            ],
        },
        "analysis_scope": [
            "trend and moving-average regime",
            "RSI, MACD, Bollinger Bands and ATR",
            "recent range references",
            "candlestick geometry labels",
            "confirmed swing highs and lows",
            "historical price-level clusters from repeated confirmed swing points",
            "source, status, timestamp and OHLCV structural diagnostics",
            "relative volume, per-observation volatility regime and historical close-to-close drawdown",
            "descriptive cross-timeframe comparison when supplied",
            "timestamp-aligned advancing/declining/unchanged market breadth when supplied",
            "descriptive weekday and calendar-month return summaries with sample counts",
        ],
        "interpretation": "Integrated historical observations and data diagnostics only. No prediction, directional signal, investment recommendation, or execution.",
        "execution": "disabled",
    }
    result["dashboard"] = build_research_dashboard(result)
    return result
