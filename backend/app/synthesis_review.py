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
SEMANTIC_REVIEW_LABELS = [
    "direct_quote", "faithful_paraphrase", "contextual_support",
    "contradicted", "unsupported", "unclear",
]


def _build_claim_review_checklist(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create blank human assessment fields; never pre-fill semantic judgments."""
    checklist = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError("Each claim must be an object.")
        text = claim.get("text")
        refs = claim.get("source_refs", [])
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Each claim text must contain 1 to 2000 characters.")
        if not isinstance(refs, list) or len(refs) > 20 or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("Claim source_refs must be a list of at most 20 strings.")
        checklist.append({
            "claim_index": index,
            "claim_text": text.strip(),
            "source_refs": sorted({ref.strip() for ref in refs if ref.strip()}),
            "semantic_assessment": None,
            "allowed_assessments": list(SEMANTIC_REVIEW_LABELS),
            "reviewer_checked_source_context": None,
            "reviewer_checked_counterevidence": None,
            "reviewer_note": "",
            "review_complete": False,
            "instructions": "A human reviewer must inspect the source in context, consider counterevidence, choose an assessment, and add notes before marking complete.",
        })
    return checklist


def validate_claim_review_checklist(checklist: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate reviewer-entered fields. This checks form completeness, not reviewer identity or truth."""
    if not isinstance(checklist, list) or len(checklist) > MAX_CLAIMS:
        raise ValueError("checklist must be a list with at most 100 claims.")
    reviewed = []
    complete_count = 0
    for index, item in enumerate(checklist):
        if not isinstance(item, dict):
            raise ValueError("Each checklist entry must be an object.")
        assessment = item.get("semantic_assessment")
        context_checked = item.get("reviewer_checked_source_context")
        counterevidence_checked = item.get("reviewer_checked_counterevidence")
        note = item.get("reviewer_note", "")
        requested_complete = item.get("review_complete", False)
        if assessment is not None and assessment not in SEMANTIC_REVIEW_LABELS:
            raise ValueError("semantic_assessment must be one of the allowed review labels.")
        if context_checked not in (None, True, False) or counterevidence_checked not in (None, True, False):
            raise ValueError("reviewer source-context and counterevidence checks must be booleans or null.")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError("reviewer_note must be a string of at most 2000 characters.")
        if not isinstance(requested_complete, bool):
            raise ValueError("review_complete must be a boolean.")
        complete = bool(
            requested_complete
            and assessment is not None
            and context_checked is True
            and counterevidence_checked is True
            and note.strip()
        )
        complete_count += int(complete)
        reviewed.append({
            "claim_index": item.get("claim_index", index),
            "semantic_assessment": assessment,
            "reviewer_checked_source_context": context_checked,
            "reviewer_checked_counterevidence": counterevidence_checked,
            "reviewer_note": note.strip(),
            "review_complete": complete,
        })
    return {
        "status": "complete" if complete_count == len(checklist) and checklist else "incomplete",
        "complete_claim_count": complete_count,
        "total_claim_count": len(checklist),
        "claims": reviewed,
        "note": "Completeness validation does not authenticate the reviewer or establish that the assessment is correct.",
    }


def build_synthesis_review_packet(
    *, draft: str, claims: list[dict[str, Any]],
    source_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prepare an evidence-aware packet; never approve or authenticate it."""
    if not isinstance(draft, str) or not draft.strip() or len(draft) > MAX_TEXT_CHARS:
        raise ValueError("draft must contain 1 to 8000 characters.")
    from .research_evidence_audit import audit_evidence
    from .research_quality_eval import evaluate_research_draft
    from .research_citation_audit import audit_claim_citations
    from .research_claim_support import audit_claim_source_overlap

    audit = audit_evidence(claims=claims, source_registry=source_registry)
    quality = evaluate_research_draft(draft=draft, claims=claims, source_registry=source_registry)
    reference_gate_passed = bool(claims) and all(
        item["reference_status"] == "registry_match" for item in audit["claims"]
    )
    disagreement_count = audit["metrics"]["claim_disagreement_candidate_count"]
    citation_audit = audit_claim_citations(claims=claims, source_registry=source_registry)
    claim_support_screen = audit_claim_source_overlap(claims=claims, source_registry=source_registry)
    claim_review_checklist = _build_claim_review_checklist(claims)
    return {
        "packet_type": "evidence_aware_synthesis_review_packet",
        "review_status": "pending_human_decision",
        "reference_gate": {
            "status": "passed" if reference_gate_passed else "blocked",
            "all_claims_have_known_source_refs": reference_gate_passed,
            "unknown_source_id_count": audit["metrics"]["unknown_source_id_count"],
            "claims_without_refs_count": sum(1 for item in audit["claims"] if item["reference_status"] == "missing"),
        },
        "review_attention": {
            "status": "attention_required" if disagreement_count else "no_disagreement_candidates_detected",
            "disagreement_candidate_count": disagreement_count,
            "note": "No detected disagreement does not establish that claims are correct or conflict-free.",
        },
        "quality_metrics": quality["metrics"],
        "evidence_audit": audit,
        "citation_audit": citation_audit,
        "claim_support_screen": claim_support_screen,
        "claim_support_gate": {
            "status": claim_support_screen["status"],
            "note": "Lexical overlap is a triage signal only; human semantic review remains mandatory.",
        },
        "claim_review_checklist": claim_review_checklist,
        "claim_review_checklist_gate": {
            "status": "human_review_required",
            "complete_claim_count": 0,
            "total_claim_count": len(claim_review_checklist),
            "note": "Checklist fields are intentionally blank; no semantic assessment is inferred or pre-approved.",
        },
        "citation_gate": {
            "status": citation_audit["status"],
            "claim_citation_coverage": citation_audit["metrics"]["claim_citation_coverage"],
            "claims_without_valid_citations": citation_audit["metrics"]["claims_without_valid_citations"],
            "note": "Exact excerpt matching is traceability only; it does not establish semantic support or truth.",
        },
        "draft": draft.strip(),
        "human_decision_required": True,
        "auto_approval": False,
        "limitations": [
            "This endpoint prepares a review packet only; it does not persist a review or record a reviewer decision.",
            "Source authenticity, claim entailment, factual correctness, and reviewer identity are not verified.",
            "A passed reference gate means identifiers match the supplied registry, not that sources substantiate claims.",
            "Citation audit checks exact excerpts against supplied source text; missing citation excerpts require human review.",
        ],
    }


def build_synthesis_review(
    *, draft: str, claims: list[dict[str, Any]], source_registry: list[dict[str, Any]],
    decision: str, reviewer: str, review_note: str = "",
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
    from .research_citation_audit import audit_claim_citations
    citation_audit = audit_claim_citations(claims=claims, source_registry=source_registry)
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
            "text": text.strip(), "source_refs": refs,
            "reference_check": "unknown_source_ids" if unknown else ("matched_registry" if refs else "missing_source_refs"),
            "unknown_source_ids": unknown, "source_authenticity_verified": False,
        })
    if decision == "approve" and (not all_claims_have_sources or any(c["unknown_source_ids"] for c in reviewed_claims)):
        raise ValueError("Approval blocked: every claim needs valid source references from the supplied registry.")
    return {
        "status": "approved" if decision == "approve" else "rejected",
        "review_gate": "human_decision_recorded", "reviewer": reviewer.strip(),
        "review_note": review_note.strip(), "draft": draft.strip(), "claims": reviewed_claims,
        "citation_audit": citation_audit,
        "citation_gate": {
            "status": citation_audit["status"],
            "claim_citation_coverage": citation_audit["metrics"]["claim_citation_coverage"],
            "claims_without_valid_citations": citation_audit["metrics"]["claims_without_valid_citations"],
            "note": "Citation provenance is saved with this review; exact excerpt matching does not establish semantic support or truth.",
        },
        "evidence_status": "source_refs_matched_but_not_authenticity_verified" if all_claims_have_sources else "incomplete_source_refs",
        "source_registry_count": len(source_ids),
        "limitations": [
            "Review result is returned but not persisted by this endpoint.",
            "Source identifiers are checked only against the supplied registry; source authenticity and claim entailment are not verified.",
            "Approval is a human workflow decision, not an investment recommendation or execution authorization.",
        ],
    }
