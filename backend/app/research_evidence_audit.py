"""Conservative evidence traceability and disagreement audit.

This module flags source duplication and explicitly keyed claim disagreements for
human review. It does not establish source independence, truth, or entailment.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from typing import Any

MAX_CLAIMS = 200
MAX_SOURCES = 500
VALID_STANCES = {"supports", "contradicts", "context"}


def _source_group(source: dict[str, Any]) -> str:
    """Return a declared independence group or a conservative URL fingerprint."""
    group = source.get("independence_group")
    if isinstance(group, str) and group.strip():
        return "declared:" + group.strip()
    url = source.get("url")
    if isinstance(url, str) and url.strip():
        parsed = urlsplit(url.strip())
        # Keep path/query: different article pages are not automatically duplicates.
        normalized = urlunsplit((
            parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"),
            parsed.query, ""
        ))
        if normalized:
            return "url:" + normalized
    # No metadata means we cannot claim independence. Group by source ID to avoid
    # falsely merging unrelated unknown sources or treating them as verified.
    return "unverified:" + str(source["source_id"])


def audit_evidence(*, claims: list[dict[str, Any]],
                   source_registry: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit references, source grouping, and explicitly keyed stance conflicts."""
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims must be a list with at most 200 entries")
    if not isinstance(source_registry, list) or len(source_registry) > MAX_SOURCES:
        raise ValueError("source_registry must be a list with at most 500 entries")

    sources: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[str]] = {}
    for source in source_registry:
        if not isinstance(source, dict):
            raise ValueError("source_registry entries must be objects")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("each source requires a non-empty source_id")
        source_id = source_id.strip()
        if source_id in sources:
            raise ValueError("source_id values must be unique")
        item = dict(source)
        item["source_id"] = source_id
        group = _source_group(item)
        sources[source_id] = item
        groups.setdefault(group, []).append(source_id)

    claim_reports = []
    keyed_stances: dict[str, list[dict[str, Any]]] = {}
    unknown_refs: set[str] = set()
    claims_with_refs = 0
    claims_with_known_refs = 0
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError("claims entries must be objects")
        text = claim.get("text")
        refs = claim.get("source_refs", [])
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("claim text must contain 1 to 4000 characters")
        if (not isinstance(refs, list) or len(refs) > 30
                or any(not isinstance(ref, str) for ref in refs)):
            raise ValueError("source_refs must be a list of at most 30 strings")
        refs = sorted({ref.strip() for ref in refs if ref.strip()})
        unknown = sorted(set(refs) - set(sources))
        known = [ref for ref in refs if ref in sources]
        source_groups = sorted({_source_group(sources[ref]) for ref in known})
        if refs:
            claims_with_refs += 1
        if refs and not unknown:
            claims_with_known_refs += 1
        unknown_refs.update(unknown)

        claim_key = claim.get("claim_key")
        stance = claim.get("stance")
        if claim_key is not None:
            if not isinstance(claim_key, str) or not claim_key.strip() or len(claim_key) > 200:
                raise ValueError("claim_key must be a non-empty string up to 200 characters")
            if stance not in VALID_STANCES:
                raise ValueError("keyed claims require stance: supports, contradicts, or context")
            if stance in {"supports", "contradicts"}:
                keyed_stances.setdefault(claim_key.strip(), []).append({
                    "claim_index": index,
                    "stance": stance,
                    "source_refs": known,
                    "source_groups": source_groups,
                })
        elif stance is not None and stance not in VALID_STANCES:
            raise ValueError("stance must be supports, contradicts, or context")

        claim_reports.append({
            "claim_index": index,
            "claim_key": claim_key.strip() if isinstance(claim_key, str) else None,
            "source_refs": refs,
            "known_source_refs": known,
            "unknown_source_refs": unknown,
            "source_group_count": len(source_groups),
            "reference_status": "missing" if not refs else ("unknown_ids" if unknown else "registry_match"),
        })

    disagreements = []
    for claim_key, entries in sorted(keyed_stances.items()):
        support = [entry for entry in entries if entry["stance"] == "supports"]
        contradict = [entry for entry in entries if entry["stance"] == "contradicts"]
        # Only report when opposing labels have evidence from distinct source
        # groups. This remains a review lead, not a verified factual contradiction.
        support_groups = {group for entry in support for group in entry["source_groups"]}
        contradict_groups = {group for entry in contradict for group in entry["source_groups"]}
        independent_group_overlap = support_groups & contradict_groups
        if support and contradict and (support_groups - independent_group_overlap) and (contradict_groups - independent_group_overlap):
            disagreements.append({
                "claim_key": claim_key,
                "supporting_claim_indices": sorted({entry["claim_index"] for entry in support}),
                "contradicting_claim_indices": sorted({entry["claim_index"] for entry in contradict}),
                "support_source_groups": sorted(support_groups),
                "contradict_source_groups": sorted(contradict_groups),
                "status": "human_review_required",
                "warning": "Stance labels are supplied metadata; this audit does not verify claim meaning or source entailment.",
            })

    denominator = len(claims) or 1
    metrics = {
        "claim_count": len(claims),
        "claim_reference_coverage": round(claims_with_refs / denominator, 4) if claims else None,
        "known_source_reference_coverage": round(claims_with_known_refs / denominator, 4) if claims else None,
        "unknown_source_id_count": len(unknown_refs),
        "source_count": len(sources),
        "source_group_count": len(groups),
        "duplicate_or_shared_source_group_count": sum(1 for ids in groups.values() if len(ids) > 1),
        "claim_disagreement_candidate_count": len(disagreements),
    }
    return {
        "audit_type": "conservative_evidence_traceability_and_disagreement_audit",
        "metrics": metrics,
        "claims": claim_reports,
        "source_groups": [
            {"group_id": group, "source_ids": sorted(ids),
             "grouping_basis": "declared_independence_group" if group.startswith("declared:")
             else ("normalized_url" if group.startswith("url:") else "source_id_fallback")}
            for group, ids in sorted(groups.items())
        ],
        "disagreement_candidates": disagreements,
        "limitations": [
            "URL or declared-group similarity is only a duplicate-dependence heuristic, not proof of common ownership or independence.",
            "Disagreement candidates rely on caller-supplied claim_key and stance labels.",
            "The audit does not verify source authenticity, claim entailment, factual truth, or whether claims are genuinely contradictory.",
            "Unknown sources and claims without explicit keys are not inferred or auto-resolved.",
        ],
    }
