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


def evaluate_research_draft(
    *,
    draft: str,
    claims: list[dict[str, Any]],
    source_registry: list[dict[str, Any]],
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(draft, str) or not draft.strip() or len(draft) > MAX_DRAFT_CHARS:
        raise ValueError("draft must contain 1 to 20000 characters")
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims must be a list with at most 200 entries")
    if not isinstance(source_registry, list) or len(source_registry) > MAX_SOURCES:
        raise ValueError("source_registry must be a list with at most 500 entries")
    if baseline is not None and not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")

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

    draft_lower = draft.lower()
    uncertainty_markers = [
        marker for marker in ("uncertain", "unknown", "limitation", "assumption",
                              "not verified", "cannot conclude", "insufficient data")
        if marker in draft_lower
    ]
    denominator = total or 1
    metrics = {
        "claim_count": total,
        "claims_with_source_refs": claims_with_refs,
        "claims_with_known_source_refs": claims_with_known_refs,
        "claim_reference_coverage": round(claims_with_refs / denominator, 4) if total else None,
        "known_source_reference_coverage": round(claims_with_known_refs / denominator, 4) if total else None,
        "unknown_source_id_count": len(unknown_refs),
        "source_registry_count": len(source_ids),
        "uncertainty_marker_count": len(uncertainty_markers),
        "uncertainty_markers": uncertainty_markers,
    }

    comparison = None
    if baseline is not None:
        base_metrics = baseline.get("metrics")
        if not isinstance(base_metrics, dict):
            raise ValueError("baseline must include a metrics object")
        supported_metrics = ("claim_reference_coverage", "known_source_reference_coverage")
        recognized_metrics = set(supported_metrics).intersection(base_metrics)
        if not recognized_metrics:
            raise ValueError("baseline metrics must include at least one supported metric")
        for metric_name in recognized_metrics:
            metric_value = base_metrics[metric_name]
            if (isinstance(metric_value, bool)
                    or not isinstance(metric_value, (int, float))
                    or not 0 <= metric_value <= 1):
                raise ValueError(
                    f"baseline metric {metric_name} must be a number between 0 and 1"
                )
        comparison = {}
        for key in supported_metrics:
            current = metrics[key]
            previous = base_metrics.get(key)
            if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                comparison[key] = {
                    "current": current,
                    "baseline": previous,
                    "delta": round(current - previous, 4),
                }
            else:
                comparison[key] = {"current": current, "baseline": previous, "delta": None}

    return {
        "evaluation_type": "deterministic_research_traceability_check",
        "metrics": metrics,
        "claims": reviewed,
        "baseline_comparison": comparison,
        "interpretation": (
            "Structural traceability only. This does not verify source authenticity, "
            "claim entailment, factual correctness, forecast accuracy, or investment value."
        ),
    }
