"""Deterministic structural quality checks for research drafts.

This module evaluates traceability and uncertainty markers, not truth, predictive
skill, market performance, or whether a cited source actually supports a claim.
It is intentionally a transparent checklist-style evaluator.
"""
from __future__ import annotations

from typing import Any

MAX_DRAFT_CHARS = 20_000
MAX_CLAIMS = 200
MAX_SOURCES = 500
SUPPORTED_BASELINE_METRICS = (
    "claim_reference_coverage",
    "known_source_reference_coverage",
)


def _validate_baseline_metrics(baseline: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate baseline metrics before inspecting the research draft."""
    if baseline is None:
        return None
    base_metrics = baseline.get("metrics")
    if not isinstance(base_metrics, dict):
        raise ValueError("baseline must include a metrics object")
    unknown_metrics = set(base_metrics) - set(SUPPORTED_BASELINE_METRICS)
    if unknown_metrics:
        raise ValueError(
            f"baseline contains unsupported metrics: {sorted(unknown_metrics)}"
        )
    if not base_metrics:
        raise ValueError("baseline metrics must include at least one supported metric")
    for metric_name, metric_value in base_metrics.items():
        if (isinstance(metric_value, bool)
                or not isinstance(metric_value, (int, float))
                or not 0 <= metric_value <= 1):
            raise ValueError(
                f"baseline metric {metric_name} must be a number between 0 and 1"
            )
    return base_metrics


def evaluate_research_draft(
    *,
    draft: str,
    claims: list[dict[str, Any]],
    source_registry: list[dict[str, Any]],
    baseline: dict[str, Any] | None = None,
    uncertainty_markers: tuple[str, ...] = ("uncertain", "unknown", "limitation", "assumption", "not verified", "cannot conclude", "insufficient data"),
) -> dict[str, Any]:
    # Validate baseline first so invalid benchmark configuration is reported
    # consistently, even when the draft or claim payload is malformed.
    if baseline is not None and not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")
    base_metrics = _validate_baseline_metrics(baseline)
    if not isinstance(draft, str) or not draft.strip() or len(draft) > MAX_DRAFT_CHARS:
        raise ValueError("draft must contain 1 to 20000 characters")
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims must be a list with at most 200 entries")
    if not isinstance(source_registry, list) or len(source_registry) > MAX_SOURCES:
        raise ValueError("source_registry must be a list with at most 500 entries")

    source_ids = set()
    for source in source_registry:
        if not isinstance(source, dict):
            raise ValueError("source_registry entries must be objects")
        source_id = source.get("source_id")
        if isinstance(source_id, str) and source_id.strip():
            source_ids.add(source_id.strip())

    total = len(claims)
    claims_with_refs = 0
    claims_with_known_refs = 0
    unknown_refs = set()
    reviewed = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("claims entries must be objects")
        text = claim.get("text")
        refs = claim.get("source_refs", [])
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("claim text must contain 1 to 4000 characters")
        if not isinstance(refs, list) or len(refs) > 30 or any(not isinstance(x, str) for x in refs):
            raise ValueError("source_refs must be a list of at most 30 strings")
        refs = sorted({x.strip() for x in refs if x.strip()})
        missing = sorted(set(refs) - source_ids)
        if refs:
            claims_with_refs += 1
        if refs and not missing:
            claims_with_known_refs += 1
        unknown_refs.update(missing)
        reviewed.append({
            "claim": text.strip(),
            "source_refs": refs,
            "reference_status": "missing" if not refs else ("unknown_ids" if missing else "registry_match"),
            "unknown_source_ids": missing,
        })

    if (not isinstance(uncertainty_markers, (tuple, list)) or not uncertainty_markers
            or len(uncertainty_markers) > 20
            or any(not isinstance(marker, str) or not marker.strip() or len(marker) > 80
                   for marker in uncertainty_markers)):
        raise ValueError("uncertainty_markers must contain 1 to 20 non-empty strings up to 80 characters")
    normalized_markers = tuple(dict.fromkeys(marker.strip().lower() for marker in uncertainty_markers))
    draft_lower = draft.lower()
    matched_uncertainty_markers = [marker for marker in normalized_markers if marker in draft_lower]
    denominator = total or 1
    metrics = {
        "claim_count": total,
        "claims_with_source_refs": claims_with_refs,
        "claims_with_known_source_refs": claims_with_known_refs,
        "claim_reference_coverage": round(claims_with_refs / denominator, 4) if total else None,
        "known_source_reference_coverage": round(claims_with_known_refs / denominator, 4) if total else None,
        "unknown_source_id_count": len(unknown_refs),
        "source_registry_count": len(source_ids),
        "uncertainty_marker_count": len(matched_uncertainty_markers),
        "uncertainty_markers": matched_uncertainty_markers,
        "uncertainty_marker_coverage": (1.0 if matched_uncertainty_markers else 0.0),
    }

    comparison = None
    comparison_summary = None
    if baseline is not None:
        comparison = {}
        skipped_comparisons = []
        for key in SUPPORTED_BASELINE_METRICS:
            current = metrics[key]
            previous = base_metrics.get(key)
            if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                comparison[key] = {
                    "current": current,
                    "baseline": previous,
                    "delta": round(current - previous, 4),
                    "status": "compared",
                }
            else:
                reason = (
                    "current_metric_unavailable"
                    if not isinstance(current, (int, float))
                    else "baseline_metric_missing"
                )
                comparison[key] = {
                    "current": current,
                    "baseline": previous,
                    "delta": None,
                    "status": "skipped",
                    "reason": reason,
                }
                skipped_comparisons.append({"metric": key, "reason": reason})
        regression_metrics = sorted(
            key for key, item in comparison.items()
            if item["status"] == "compared" and item["delta"] < 0
        )
        comparison_summary = {
            "status": (
                "comparison_incomplete" if skipped_comparisons
                else ("regression_detected" if regression_metrics else "comparison_complete")
            ),
            "skipped_comparison_count": len(skipped_comparisons),
            "skipped_comparisons": skipped_comparisons,
            "regression_metric_count": len(regression_metrics),
            "regression_metrics": regression_metrics,
            "note": "For these coverage metrics, lower values indicate regression. Skipped comparisons are not evidence of a pass.",
        }

    return {
        "evaluation_type": "deterministic_research_traceability_check",
        "metrics": metrics,
        "claims": reviewed,
        "baseline_comparison": comparison,
        "baseline_comparison_summary": comparison_summary,
        "interpretation": (
            "Structural traceability only. This does not verify source authenticity, "
            "claim entailment, factual correctness, forecast accuracy, or investment value."
        ),
    }
