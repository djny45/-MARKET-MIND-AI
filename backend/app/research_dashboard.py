"""Compact summary layer for integrated descriptive research reports."""


def build_research_dashboard(report: dict) -> dict:
    timeframes = report.get("timeframes", {})
    timeframe_cards = []
    quality_counts = {"no_structural_issues_detected": 0, "issues_detected": 0}
    cluster_totals = {"historical_swing_high": 0, "historical_swing_low": 0}

    for interval, section in timeframes.items():
        quality = section.get("data_quality") or {}
        quality_status = quality.get("quality_status", "unavailable")
        if quality_status in quality_counts:
            quality_counts[quality_status] += 1

        chart = section.get("chart_research") or {}
        indicators = chart.get("indicators") or {}
        structure = chart.get("observed_structure") or {}
        clusters = section.get("historical_price_clusters") or {}
        cluster_map = clusters.get("clusters") or {}
        for side in cluster_totals:
            cluster_totals[side] += len(cluster_map.get(side, []))

        timeframe_cards.append({
            "interval": interval,
            "status": "available" if chart and chart.get("mode") == "descriptive_research_only" else "unavailable_or_insufficient",
            "latest_bar_timestamp": chart.get("latest_bar_timestamp"),
            "latest_close": chart.get("latest_close"),
            "moving_average_regime": structure.get("moving_average_regime"),
            "rsi14": indicators.get("rsi14"),
            "atr14": indicators.get("atr14"),
            "data_quality_status": quality_status,
            "bars_checked": quality.get("bars_checked", 0),
            "historical_high_clusters": len(cluster_map.get("historical_swing_high", [])),
            "historical_low_clusters": len(cluster_map.get("historical_swing_low", [])),
            "warnings": chart.get("warnings", []),
        })

    correlation = report.get("cross_asset_correlation")
    correlation_summary = None
    if correlation:
        matrix = correlation.get("pearson_return_correlation", {})
        observations = correlation.get("paired_return_observations", {})
        pairs = []
        symbols = correlation.get("symbols", [])
        for index, left in enumerate(symbols):
            for right in symbols[index + 1:]:
                pairs.append({
                    "symbols": [left, right],
                    "correlation": (matrix.get(left) or {}).get(right),
                    "paired_observations": (observations.get(left) or {}).get(right, 0),
                })
        correlation_summary = {"symbols": symbols, "pairs": pairs}

    breadth = report.get("market_breadth")
    breadth_latest = breadth.get("latest_observation") if breadth else None

    return {
        "mode": "consolidated_descriptive_research_dashboard",
        "symbol": report.get("symbol"),
        "timeframes": timeframe_cards,
        "data_quality": {
            "timeframes_checked": len(timeframes),
            "no_structural_issues_detected": quality_counts["no_structural_issues_detected"],
            "timeframes_with_issues": quality_counts["issues_detected"],
            "timeframes_without_chart_analysis": len(report.get("coverage", {}).get("timeframes_with_insufficient_bars", [])),
        },
        "historical_price_clusters": {
            "confirmed_swing_high_cluster_count": cluster_totals["historical_swing_high"],
            "confirmed_swing_low_cluster_count": cluster_totals["historical_swing_low"],
            "note": "Historical price concentrations only; not guaranteed support, resistance or future targets.",
        },
        "cross_asset_correlation": correlation_summary,
        "market_breadth_latest": breadth_latest,
        "cross_timeframe_available": report.get("cross_timeframe") is not None,
        "limitations": [
            "This dashboard summarizes the supplied deep report and does not fetch or validate new market data.",
            "A timeframe's latest stored observation is not assumed to be current or fresh.",
            "Missing or unavailable sections remain explicitly unavailable; no values are inferred.",
            "All outputs are historical descriptive research, not forecasts, investment recommendations or execution instructions.",
        ],
        "execution": "disabled",
    }
