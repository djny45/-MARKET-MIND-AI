"""Portable evidence bundle and human-readable methodology report; no forecasts or orders."""
import hashlib
import json
import re

from .historical_quality import build_historical_quality_diagnostics
from .source_comparison import compare_source_observations
from .research_timeline import build_research_timeline


def build_research_evidence_bundle(symbol, interval, history, deep_report=None):
    """Assemble reproducible inputs and diagnostics while retaining source provenance."""
    quality = build_historical_quality_diagnostics(history)
    comparison = compare_source_observations(history)
    try:
        timeline = build_research_timeline(history, max(1, min(1000, len(history.get("bars", [])))))
    except ValueError as exc:
        # Preserve malformed source rows in the evidence bundle; timeline
        # annotations are optional diagnostics and must not hide bad data.
        timeline = {
            "status": "unavailable_invalid_ohlcv",
            "events": [],
            "bars_included": 0,
            "validation_error": str(exc),
            "execution": "disabled",
        }
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



def _escape_markdown_inline(value):
    """Escape untrusted metadata before inserting it into Markdown prose."""
    text = str(value).replace("\\", "\\\\")
    for char in ("`", "*", "_", "[", "]", "|", "#"):
        text = text.replace(char, "\\" + char)
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("\r", " ").replace("\n", " ")


def _markdown_json_block(value):
    """Fence JSON safely even when untrusted values contain Markdown backticks."""
    longest_run = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}json\n{value}\n{fence}"


def render_research_methodology_markdown(bundle):
    """Render a reproducible Markdown summary from a historical evidence bundle."""
    if not isinstance(bundle, dict) or bundle.get("report_type") != "historical_research_evidence":
        raise ValueError("bundle must be a historical_research_evidence object")
    scope_value = bundle.get("scope")
    scope = scope_value if isinstance(scope_value, dict) else {}
    source_values = scope.get("sources")
    if isinstance(source_values, (list, tuple)):
        sources = source_values
    elif isinstance(source_values, str) and source_values:
        sources = [source_values]
    else:
        sources = [scope.get("source")] if scope.get("source") else []
    integrity_value = bundle.get("integrity")
    integrity = integrity_value if isinstance(integrity_value, dict) else {}
    data_quality_json = json.dumps(
        bundle.get("data_quality") or {}, ensure_ascii=False, indent=2, allow_nan=False
    )
    source_comparison_json = json.dumps(
        bundle.get("source_comparison") or {}, ensure_ascii=False, indent=2, allow_nan=False
    )
    lines = [f"# Historical Research Report: {_escape_markdown_inline(scope.get('symbol') or 'Unknown')}", "",
        "## Scope and provenance",
        f"- **Symbol:** {_escape_markdown_inline(scope.get('symbol') or 'Not supplied')}",
        f"- **Interval:** {_escape_markdown_inline(scope.get('interval') or 'Not supplied')}",
        f"- **Observations:** {_escape_markdown_inline(scope.get('observation_count', 0))}",
        f"- **Status:** {_escape_markdown_inline(scope.get('status') or 'Not supplied')}",
        f"- **Source metadata:** {', '.join(_escape_markdown_inline(x) for x in sources) if sources else 'Not supplied'}",
        f"- **Retrieved at:** {_escape_markdown_inline(scope.get('retrieved_at') or 'Not supplied')}",
        f"- **Time range:** {_escape_markdown_inline(scope.get('first_timestamp') or 'Not supplied')} to {_escape_markdown_inline(scope.get('last_timestamp') or 'Not supplied')}",
        "", "## Methodology",
        "- Uses observations preserved in the supplied evidence bundle.",
        "- Includes deterministic quality diagnostics, source comparisons, and the descriptive timeline below.",
        "- Source labels are supplied metadata, not independent source verification.",
        "", "## Descriptive timeline",
        _markdown_json_block(json.dumps(bundle.get("timeline") or {}, ensure_ascii=False, indent=2, allow_nan=False)),
        "", "## Data-quality diagnostics",
        _markdown_json_block(data_quality_json),
        "", "## Source comparison",
        _markdown_json_block(source_comparison_json),
        "", "## Integrity",
        f"- **Algorithm:** {_escape_markdown_inline(integrity.get('algorithm') or 'Not supplied')}",
        f"- **Digest:** {_escape_markdown_inline(integrity.get('digest') or 'Not supplied')}",
        "", "## Limitations"]
    limitations = bundle.get("limitations")
    if not isinstance(limitations, list):
        limitations = ["Limitations not supplied."]
    lines.extend(f"- {_escape_markdown_inline(item)}" for item in limitations)
    lines.extend(["", "> Research documentation only—not a forecast, investment recommendation, or trading instruction.", ""])
    return "\n".join(lines)
