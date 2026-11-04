"""Portable evidence bundle and human-readable methodology report; no forecasts or orders."""
import hashlib
import json

from .historical_quality import build_historical_quality_diagnostics
from .source_comparison import compare_source_observations
from .research_timeline import build_research_timeline


def build_research_evidence_bundle(symbol, interval, history, deep_report=None):
    """Assemble reproducible inputs and diagnostics while retaining source provenance."""
    quality = build_historical_quality_diagnostics(history)
    comparison = compare_source_observations(history)
    timeline = build_research_timeline(history, max(1, min(1000, len(history.get("bars", [])))))
    bundle = {
        "schema_version": "1.1", "report_type": "historical_research_evidence",
        "scope": {"symbol": symbol.strip().upper(), "interval": interval,
            "observation_count": len(history.get("bars", [])), "source": history.get("source"),
            "sources": history.get("sources", []), "status": history.get("status"),
            "retrieved_at": history.get("retrieved_at"), "first_timestamp": history.get("first_timestamp"),
            "last_timestamp": history.get("last_timestamp")},
        "observations": history.get("bars", []), "data_quality": quality,
        "source_comparison": comparison, "timeline": timeline, "deep_research": deep_report,
        "limitations": ["Historical observations and deterministic diagnostics only.",
            "Source authenticity, licensing, completeness and freshness are not independently certified.",
            "No missing observations are inferred, interpolated or fabricated.",
            "No forecasts, directional signals, investment recommendations or orders are produced."]}
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    bundle["integrity"] = {"algorithm": "sha256",
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "scope": "complete evidence bundle excluding this integrity field",
        "canonicalization": "UTF-8 JSON with sorted keys and compact separators"}
    return bundle


def render_research_methodology_markdown(bundle):
    """Render a reproducible Markdown summary from a historical evidence bundle."""
    if not isinstance(bundle, dict) or bundle.get("report_type") != "historical_research_evidence":
        raise ValueError("bundle must be a historical_research_evidence object")
    scope = bundle.get("scope") or {}
    sources = scope.get("sources") or ([scope.get("source")] if scope.get("source") else [])
    integrity = bundle.get("integrity") or {}
    data_quality_json = json.dumps(
        bundle.get("data_quality") or {}, ensure_ascii=False, indent=2, allow_nan=False
    )
    source_comparison_json = json.dumps(
        bundle.get("source_comparison") or {}, ensure_ascii=False, indent=2, allow_nan=False
    )
    lines = [f"# Historical Research Report: {scope.get('symbol') or 'Unknown'}", "",
        "## Scope and provenance",
        f"- **Symbol:** {scope.get('symbol') or 'Not supplied'}",
        f"- **Interval:** {scope.get('interval') or 'Not supplied'}",
        f"- **Observations:** {scope.get('observation_count', 0)}",
        f"- **Status:** {scope.get('status') or 'Not supplied'}",
        f"- **Source metadata:** {', '.join(str(x) for x in sources) if sources else 'Not supplied'}",
        f"- **Retrieved at:** {scope.get('retrieved_at') or 'Not supplied'}",
        f"- **Time range:** {scope.get('first_timestamp') or 'Not supplied'} to {scope.get('last_timestamp') or 'Not supplied'}",
        "", "## Methodology",
        "- Uses observations preserved in the supplied evidence bundle.",
        "- Includes deterministic quality diagnostics, source comparisons, and a descriptive timeline.",
        "- Source labels are supplied metadata, not independent source verification.",
        "", "## Data-quality diagnostics",
        "```json",
        data_quality_json,
        "```",
        "", "## Source comparison",
        "```json",
        source_comparison_json,
        "```",
        "", "## Integrity",
        f"- **Algorithm:** {integrity.get('algorithm') or 'Not supplied'}",
        f"- **Digest:** {integrity.get('digest') or 'Not supplied'}",
        "", "## Limitations"]
    lines.extend(f"- {item}" for item in (bundle.get("limitations") or ["Limitations not supplied."]))
    lines.extend(["", "> Research documentation only—not a forecast, investment recommendation, or trading instruction.", ""])
    return "\n".join(lines)
