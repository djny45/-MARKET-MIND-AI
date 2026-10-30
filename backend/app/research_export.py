"""Portable evidence bundle for stored historical research; no forecasts or orders."""

from .historical_quality import build_historical_quality_diagnostics
from .source_comparison import compare_source_observations
from .research_timeline import build_research_timeline


def build_research_evidence_bundle(symbol, interval, history, deep_report=None):
    """Assemble reproducible inputs and diagnostics while retaining source provenance."""
    quality = build_historical_quality_diagnostics(history)
    comparison = compare_source_observations(history)
    timeline = build_research_timeline(history, max(1, min(1000, len(history.get("bars", [])))))
    return {
        "schema_version": "1.0",
        "report_type": "historical_research_evidence",
        "scope": {
            "symbol": symbol.strip().upper(),
            "interval": interval,
            "observation_count": len(history.get("bars", [])),
            "source": history.get("source"),
            "sources": history.get("sources", []),
            "status": history.get("status"),
            "retrieved_at": history.get("retrieved_at"),
            "first_timestamp": history.get("first_timestamp"),
            "last_timestamp": history.get("last_timestamp"),
        },
        "observations": history.get("bars", []),
        "data_quality": quality,
        "source_comparison": comparison,
        "timeline": timeline,
        "deep_research": deep_report,
        "limitations": [
            "Historical observations and deterministic diagnostics only.",
            "Source authenticity, licensing, completeness and freshness are not independently certified.",
            "No missing observations are inferred, interpolated or fabricated.",
            "No forecasts, directional signals, investment recommendations or orders are produced.",
        ],
    }
