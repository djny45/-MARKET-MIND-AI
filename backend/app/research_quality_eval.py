"""Deterministic structural quality checks for research drafts.

This module evaluates traceability and uncertainty markers, not truth, predictive
skill, market performance, or whether a cited source actually supports a claim.
It is intentionally a transparent checklist-style evaluator.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime
from urllib.parse import urlparse
import re

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
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("each source requires a non-empty source_id")
        normalized_source_id = source_id.strip()
        if normalized_source_id in source_ids:
            raise ValueError("source_id values must be unique")
        source_ids.add(normalized_source_id)

        # Optional source identity metadata is validated when supplied. The
        # registry remains backward-compatible with ID-only fixtures, but
        # incomplete metadata is surfaced rather than silently trusted.
        title = source.get("title")
        if title is not None and (
            not isinstance(title, str) or not title.strip() or len(title) > 500
        ):
            raise ValueError("source title must contain 1 to 500 characters")
        publisher = source.get("publisher")
        if publisher is not None and (
            not isinstance(publisher, str) or not publisher.strip() or len(publisher) > 200
        ):
            raise ValueError("source publisher must contain 1 to 200 characters")
        source_url = source.get("url")
        if source_url is not None:
            if not isinstance(source_url, str) or len(source_url) > 2048:
                raise ValueError("source url must be a valid HTTP(S) URL")
            parsed_url = urlparse(source_url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ValueError("source url must be a valid HTTP(S) URL")
        retrieved_at = source.get("retrieved_at")
        if retrieved_at is not None:
            if not isinstance(retrieved_at, str):
                raise ValueError("source retrieved_at must be timezone-aware ISO-8601")
            try:
                parsed_timestamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("source retrieved_at must be timezone-aware ISO-8601") from exc
            if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
                raise ValueError("source retrieved_at must be timezone-aware ISO-8601")
        content_hash = source.get("content_sha256")
        if content_hash is not None and (
            not isinstance(content_hash, str) or re.fullmatch(r"[0-9a-fA-F]{64}", content_hash) is None
        ):
            raise ValueError("source content_sha256 must be a 64-character hexadecimal digest")

    source_metadata_complete = sum(
        all(source.get(field) for field in ("title", "url", "publisher", "retrieved_at", "content_sha256"))
        for source in source_registry
    )
    total = len(claims)
    claims_with_refs = 0
    claims_with_known_refs = 0
    unknown_refs = set()
    reviewed = []
    claims_with_excerpts = 0
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
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > 30:
            raise ValueError("claim evidence must be a list of at most 30 entries")
        evidence_sources = set()
        evidence_unknown = set()
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("claim evidence entries must be objects")
            evidence_source_id = item.get("source_id")
            excerpt = item.get("excerpt")
            if not isinstance(evidence_source_id, str) or not evidence_source_id.strip():
                raise ValueError("claim evidence requires a non-empty source_id")
            if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 2000:
                raise ValueError("claim evidence excerpt must contain 1 to 2000 characters")
            evidence_source_id = evidence_source_id.strip()
            evidence_sources.add(evidence_source_id)
            if evidence_source_id not in source_ids:
                evidence_unknown.add(evidence_source_id)
        evidence_unknown = sorted(evidence_unknown)
        orphaned_evidence = sorted(evidence_sources - set(refs))
        if evidence and not evidence_unknown and not orphaned_evidence:
            claims_with_excerpts += 1
        evidence_status = (
            "missing" if not evidence else
            ("unknown_source_ids" if evidence_unknown else
             ("not_in_source_refs" if orphaned_evidence else "provided_excerpt"))
        )
        reviewed.append({
            "claim": text.strip(),
            "source_refs": refs,
            "reference_status": "missing" if not refs else ("unknown_ids" if missing else "registry_match"),
            "unknown_source_ids": missing,
            "evidence_status": evidence_status,
            "evidence_source_ids": sorted(evidence_sources),
            "unknown_evidence_source_ids": evidence_unknown,
            "evidence_refs_not_in_source_refs": orphaned_evidence,
            "provided_excerpt_count": len(evidence),
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
        "claims_with_provided_excerpts": claims_with_excerpts,
        "claim_excerpt_coverage": round(claims_with_excerpts / denominator, 4) if total else None,
        "claim_reference_coverage": round(claims_with_refs / denominator, 4) if total else None,
        "known_source_reference_coverage": round(claims_with_known_refs / denominator, 4) if total else None,
        "unknown_source_id_count": len(unknown_refs),
        "source_registry_count": len(source_ids),
        "sources_with_complete_identity_metadata": source_metadata_complete,
        "source_identity_metadata_coverage": (round(source_metadata_complete / len(source_ids), 4) if source_ids else None),
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
