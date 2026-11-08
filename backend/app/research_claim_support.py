"""Transparent lexical claim/source overlap screening.

This is a low-cost triage heuristic only. Token overlap is not entailment:
it cannot reliably detect paraphrase, negation, context, or factual truth.
Low overlap should trigger review, never automatic rejection or approval.
"""
from __future__ import annotations

import re
from typing import Any

MAX_CLAIMS = 100
MAX_SOURCES = 500
MAX_CITATIONS = 20
MAX_TEXT_CHARS = 4000
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "to", "was",
    "were", "with", "this", "these", "those", "their", "has", "have",
    "had", "not", "no", "but", "can", "could", "may", "might", "will",
    "would", "should", "than", "then", "also", "into", "over", "under",
}


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1 and token not in _STOPWORDS
    }


def audit_claim_source_overlap(
    *, claims: list[dict[str, Any]], source_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report token overlap for cited source text, without claiming semantic support."""
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims must be a list with at most 100 items")
    if not isinstance(source_registry, list) or len(source_registry) > MAX_SOURCES:
        raise ValueError("source_registry must be a list with at most 500 items")

    sources: dict[str, dict[str, Any]] = {}
    for source in source_registry:
        if not isinstance(source, dict):
            raise ValueError("source_registry entries must be objects")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("each source requires a non-empty source_id")
        source_id = source_id.strip()
        if source_id in sources:
            raise ValueError("source_id values must be unique")
        sources[source_id] = source

    reports = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError("claims entries must be objects")
        claim_text = claim.get("text")
        if not isinstance(claim_text, str) or not claim_text.strip() or len(claim_text) > MAX_TEXT_CHARS:
            raise ValueError("claim text must contain 1 to 4000 characters")
        refs = claim.get("source_refs", [])
        if not isinstance(refs, list) or len(refs) > MAX_CITATIONS or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("source_refs must be a list of at most 20 strings")

        claim_tokens = _tokens(claim_text)
        source_reports = []
        for source_id in sorted({ref.strip() for ref in refs if ref.strip()}):
            source = sources.get(source_id)
            if source is None:
                source_reports.append({
                    "source_id": source_id, "status": "unknown_source_id",
                    "overlap_score": None, "shared_terms": [],
                })
                continue
            source_text = source.get("text") or source.get("content") or source.get("excerpt")
            if not isinstance(source_text, str) or not source_text.strip():
                source_reports.append({
                    "source_id": source_id, "status": "source_text_unavailable",
                    "overlap_score": None, "shared_terms": [],
                })
                continue
            source_tokens = _tokens(source_text)
            shared = sorted(claim_tokens & source_tokens)
            score = round(len(shared) / len(claim_tokens), 4) if claim_tokens else None
            source_reports.append({
                "source_id": source_id,
                "status": "lexical_overlap_screened",
                "claim_token_count": len(claim_tokens),
                "shared_term_count": len(shared),
                "shared_terms": shared[:50],
                "overlap_score": score,
                "note": "Lexical overlap is not evidence of entailment or correctness.",
            })
        reports.append({
            "claim_index": index,
            "claim_text": claim_text.strip(),
            "source_count": len(source_reports),
            "sources": source_reports,
            "status": "needs_human_semantic_review",
        })

    return {
        "audit_type": "lexical_claim_source_overlap_screen",
        "status": "screened_not_semantically_verified",
        "claims": reports,
        "limitations": [
            "Token overlap is a weak lexical heuristic, not semantic entailment.",
            "It may miss valid paraphrases or flag unrelated text with shared vocabulary.",
            "It does not evaluate negation, source context, authenticity, truth, or investment value.",
            "No score can approve a claim; human semantic review remains mandatory.",
        ],
    }
