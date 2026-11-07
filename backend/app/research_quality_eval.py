"""Deterministic structural quality checks for research drafts.

This module evaluates traceability and uncertainty markers, not truth, predictive
skill, market performance, or whether a cited source actually supports a claim.
It is intentionally a transparent checklist-style evaluator.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from datetime import datetime

MAX_DRAFT_CHARS = 20_000
MAX_CLAIMS = 200
MAX_SOURCES = 500
PROVENANCE_FIELDS = ("title", "url", "source_type", "observed_at")


def _valid_source_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def _valid_observed_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    candidate = value.strip()
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


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
    source_provenance_complete = {}
    duplicate_source_ids = set()
    source_entries_without_id = 0
    entries_missing_provenance = 0
    missing_provenance_by_field = {field: 0 for field in PROVENANCE_FIELDS}
    invalid_provenance_by_field = {"url": 0, "observed_at": 0}
    for source in source_registry:
        if not isinstance(source, dict):
            raise ValueError("source_registry entries must be objects")
        missing_fields = [
            field for field in PROVENANCE_FIELDS
            if not isinstance(source.get(field), str) or not source[field].strip()
        ]
        if missing_fields:
            entries_missing_provenance += 1
            for field in missing_fields:
                missing_provenance_by_field[field] += 1
        invalid_fields = []
        if "url" not in missing_fields and not _valid_source_url(source.get("url")):
            invalid_fields.append("url")
        if "observed_at" not in missing_fields and not _valid_observed_at(source.get("observed_at")):
            invalid_fields.append("observed_at")
        for field in invalid_fields:
            invalid_provenance_by_field[field] += 1

        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            source_entries_without_id += 1
            continue
        normalized_id = source_id.strip()
        if normalized_id in source_ids:
            duplicate_source_ids.add(normalized_id)
            # Duplicate IDs are ambiguous: treat the ID as provenance-incomplete
            # if any registry entry carrying it lacks required fields.
            source_provenance_complete[normalized_id] = (
                source_provenance_complete[normalized_id]
                and not missing_fields and not invalid_fields
            )
        else:
            source_provenance_complete[normalized_id] = (
                not missing_fields and not invalid_fields
            )
        source_ids.add(normalized_id)

    total = len(claims)
    claims_with_refs = 0
    claims_with_known_refs = 0
    claims_with_complete_provenance_refs = 0
    claims_with_incomplete_provenance_refs = 0
    incomplete_provenance_refs = set()
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
        incomplete = sorted(
            ref for ref in set(refs) & source_ids
            if not source_provenance_complete.get(ref, False)
        )
        if refs:
            claims_with_refs += 1
        if refs and not missing:
            claims_with_known_refs += 1
        if refs and not missing and not incomplete:
            claims_with_complete_provenance_refs += 1
        if refs and incomplete:
            claims_with_incomplete_provenance_refs += 1
        unknown_refs.update(missing)
        incomplete_provenance_refs.update(incomplete)
        if not refs:
            reference_status = "missing"
        elif missing:
            reference_status = "unknown_ids"
        elif incomplete:
            reference_status = "registry_match_incomplete_provenance"
        else:
            reference_status = "registry_match_complete_provenance"
        reviewed.append({
            "claim": text.strip(),
            "source_refs": refs,
            "reference_status": reference_status,
            "unknown_source_ids": missing,
            "incomplete_provenance_source_ids": incomplete,
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
        "claims_with_complete_source_provenance_refs": claims_with_complete_provenance_refs,
        "claims_with_incomplete_source_provenance_refs": claims_with_incomplete_provenance_refs,
        "incomplete_source_provenance_id_count": len(incomplete_provenance_refs),
        "incomplete_source_provenance_ids": sorted(incomplete_provenance_refs),
        "claim_reference_coverage": round(claims_with_refs / denominator, 4) if total else None,
        "known_source_reference_coverage": round(claims_with_known_refs / denominator, 4) if total else None,
        "unknown_source_id_count": len(unknown_refs),
        "source_registry_count": len(source_ids),
        "source_registry_entries_without_id_count": source_entries_without_id,
        "source_registry_entries_missing_provenance_count": entries_missing_provenance,
        "source_registry_missing_provenance_by_field": missing_provenance_by_field,
        "source_registry_invalid_provenance_by_field": invalid_provenance_by_field,
        "duplicate_source_id_count": len(duplicate_source_ids),
        "duplicate_source_ids": sorted(duplicate_source_ids),
        "uncertainty_marker_count": len(uncertainty_markers),
        "uncertainty_markers": uncertainty_markers,
    }

    comparison = None
    if baseline is not None:
        base_metrics = baseline.get("metrics")
        if not isinstance(base_metrics, dict):
            raise ValueError("baseline must include a metrics object")
        comparison = {}
        for key in ("claim_reference_coverage", "known_source_reference_coverage"):
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
            "Structural traceability only. URL and timestamp checks validate format only; " 
            "Provenance field presence is not source validation. "
            "This does not verify source authenticity, claim entailment, factual correctness, "
            "forecast accuracy, or investment value."
        ),
    }
