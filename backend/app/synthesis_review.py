"""Evidence and human-review gate for shared-core research synthesis.

Model text is an untrusted draft. This module never verifies source authenticity;
it only checks that cited source identifiers exist in the evidence bundle supplied
for this review and records the human's explicit decision in a response object.
"""
from __future__ import annotations

from typing import Any


VALID_DECISIONS = {"approve", "reject"}
MAX_CLAIMS = 100
MAX_TEXT_CHARS = 8_000


def build_synthesis_review(
    *,
    draft: str,
    claims: list[dict[str, Any]],
    source_registry: list[dict[str, Any]],
    decision: str,
    reviewer: str,
    review_note: str = "",
) -> dict[str, Any]:
    """Validate references and return a review result without persisting it."""
    if not isinstance(draft, str) or not draft.strip() or len(draft) > MAX_TEXT_CHARS:
        raise ValueError("draft must contain 1 to 8000 characters.")
    if decision not in VALID_DECISIONS:
        raise ValueError("decision must be approve or reject.")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer.strip()) > 120:
        raise ValueError("reviewer must contain 1 to 120 characters.")
    if not isinstance(review_note, str) or len(review_note) > 1000:
        raise ValueError("review_note must be at most 1000 characters.")
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims must be a list with at most 100 items.")
    if not isinstance(source_registry, list) or len(source_registry) > 500:
        raise ValueError("source_registry must be a list with at most 500 items.")

    source_ids = set()
    for source in source_registry:
        if not isinstance(source, dict):
            raise ValueError("Each source registry entry must be an object.")
        source_id = source.get("source_id")
        if isinstance(source_id, str) and source_id.strip():
            source_ids.add(source_id.strip())

    reviewed_claims = []
    all_claims_have_sources = bool(claims)
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Each claim must be an object.")
        text = claim.get("text")
        refs = claim.get("source_refs", [])
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Each claim text must contain 1 to 2000 characters.")
        if not isinstance(refs, list) or len(refs) > 20 or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("Claim source_refs must be a list of at most 20 strings.")
        refs = sorted({ref.strip() for ref in refs if ref.strip()})
        unknown = sorted(set(refs) - source_ids)
        if not refs:
            all_claims_have_sources = False
        reviewed_claims.append({
            "text": text.strip(),
            "source_refs": refs,
            "reference_check": "unknown_source_ids" if unknown else ("matched_registry" if refs else "missing_source_refs"),
            "unknown_source_ids": unknown,
            "source_authenticity_verified": False,
        })

    if decision == "approve" and (not all_claims_have_sources or any(c["unknown_source_ids"] for c in reviewed_claims)):
        raise ValueError("Approval blocked: every claim needs valid source references from the supplied registry.")

    return {
        "status": "approved" if decision == "approve" else "rejected",
        "review_gate": "human_decision_recorded",
        "reviewer": reviewer.strip(),
        "review_note": review_note.strip(),
        "draft": draft.strip(),
        "claims": reviewed_claims,
        "evidence_status": "source_refs_matched_but_not_authenticity_verified" if all_claims_have_sources else "incomplete_source_refs",
        "source_registry_count": len(source_ids),
        "limitations": [
            "Review result is returned but not persisted by this endpoint.",
            "Source identifiers are checked only against the supplied registry; source authenticity and claim entailment are not verified.",
            "Approval is a human workflow decision, not an investment recommendation or execution authorization.",
        ],
    }
