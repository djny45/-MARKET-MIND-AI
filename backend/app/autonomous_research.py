"""Autonomous, provider-injected market research loop.

This module connects discovery, approved market-data adapters, chart analysis,
and the single shared intelligence core. It selects research targets only:
no trading signals, recommendations, brokerage access, or order execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .chart_research import build_chart_report
from .intelligence_core import synthesize_research
from .market_data import MarketDataAdapter
from .market_discovery import MarketCandidate, prioritize_for_research

DEFAULT_INTERVALS = ("15m", "1h", "4h", "1d")


async def run_autonomous_research(
    candidates: Iterable[MarketCandidate],
    adapter: MarketDataAdapter,
    *,
    now: datetime | None = None,
    max_age_hours: float = 24,
    research_limit: int = 10,
    bars_limit: int = 250,
    intervals: tuple[str, ...] = DEFAULT_INTERVALS,
    use_shared_ai: bool = False,
) -> dict:
    """Prioritize fresh candidates and produce per-symbol/timeframe chart reports.

    Adapter calls are isolated: one provider failure does not discard other
    symbols or intervals. Synthetic observations are marked and excluded from
    any claim of real-market evidence. AI synthesis is opt-in and only receives
    the already-built deterministic report.
    """
    if bars_limit < 2 or bars_limit > 5000:
        raise ValueError("bars_limit must be between 2 and 5000")
    if not intervals or any(i not in {"15m", "1h", "4h", "1d"} for i in intervals):
        raise ValueError("intervals must contain supported intervals only")
    if len(set(intervals)) != len(intervals):
        raise ValueError("intervals must not contain duplicates")

    candidate_list = list(candidates)
    current_time = now or datetime.now(timezone.utc)
    queue = prioritize_for_research(
        candidate_list, now=current_time, max_age_hours=max_age_hours,
        limit=research_limit,
    )
    results = []
    for priority in queue:
        timeframe_reports = {}
        errors = {}
        provenance = {}
        for interval in intervals:
            try:
                batch = await adapter.get_bars(priority.symbol, interval, bars_limit)
                # Pydantic model contract is checked before any analysis.
                if batch.symbol.upper() != priority.symbol.upper():
                    raise ValueError(
                        f"adapter returned symbol {batch.symbol!r} for {priority.symbol!r}"
                    )
                if batch.interval != interval:
                    raise ValueError(
                        f"adapter returned interval {batch.interval!r} for {interval!r}"
                    )
                bars = [bar.model_dump(mode="json") for bar in batch.bars]
                history = {"symbol": batch.symbol, "interval": batch.interval, "bars": bars}
                report = build_chart_report(history)
                report["data_status"] = batch.status.value
                report["data_source"] = batch.source
                report["retrieved_at"] = batch.retrieved_at.isoformat()
                report["adapter_warnings"] = list(batch.warnings)
                timeframe_reports[interval] = report
                provenance[interval] = {
                    "status": batch.status.value,
                    "source": batch.source,
                    "retrieved_at": batch.retrieved_at.isoformat(),
                    "bars_received": len(batch.bars),
                }
            except Exception as exc:
                # Keep failure local to the affected symbol/timeframe.
                errors[interval] = f"{type(exc).__name__}: {exc}"

        results.append({
            "symbol": priority.symbol,
            "venue": priority.venue,
            "asset_class": next(
                (c.asset_class for c in candidate_list
                 if c.symbol.strip().upper() == priority.symbol
                 and c.venue.strip().lower() == priority.venue.strip().lower()),
                "unknown",
            ),
            "research_priority": {
                "score": priority.score,
                "confidence": priority.confidence,
                "reasons": list(priority.reasons),
                "missing_evidence": list(priority.missing_evidence),
            },
            "timeframes": timeframe_reports,
            "provenance": provenance,
            "errors": errors,
            "status": "completed" if timeframe_reports and not errors else (
                "partial" if timeframe_reports else "failed"
            ),
        })

    report = {
        "mode": "autonomous_descriptive_market_research",
        "generated_at": current_time.isoformat(),
        "adapter": getattr(adapter, "name", type(adapter).__name__),
        "candidates_received": len(candidate_list),
        "research_queue_size": len(queue),
        "results": results,
        "limitations": [
            "Research priority selects what to inspect, not what to buy or sell.",
            "Provider coverage, licensing, freshness, and rate limits depend on the injected adapter.",
            "News/social correlation is not performed by this module; it requires separately validated source/entity matching.",
            "No prediction, financial advice, live trading, brokerage access, or order execution.",
        ],
        "execution": "disabled",
    }
    if use_shared_ai:
        report["shared_ai_synthesis"] = synthesize_research(report)
    else:
        report["shared_ai_synthesis"] = {
            "status": "not_requested",
            "note": "Deterministic chart research remains authoritative; shared AI synthesis is opt-in.",
        }
    return report
