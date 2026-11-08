"""Evidence-grounded citation coverage checks for research synthesis.

Checks that claim citations point to supplied source records and that quoted
excerpts are exact substrings of caller-provided source text. It does NOT verify
source authenticity, claim entailment, or factual truth.
"""
from __future__ import annotations

from typing import Any

MAX_CLAIMS = 100
MAX_SOURCES = 500
MAX_CITATIONS_PER_CLAIM = 20
MAX_EXCERPT_CHARS = 1200


def audit_claim_citations(*, claims: list[dict[str, Any]],
                          source_registry: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims must be a list with at most 100 items")
    if not isinstance(source_registry, list) or len(source_registry) > MAX_SOURCES:
        raise ValueError("source_registry must be a list with at most 500 items")

    sources: dict[str, dict[str, Any]] = {}
    for source in source_registry:
        if not isinstance(source, dict):
            raise ValueError("source_registry entries must be objects")
        sid = source.get("source_id")
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError("each source requires a non-empty source_id")
        sid = sid.strip()
        if sid in sources:
            raise ValueError("source_id values must be unique")
        sources[sid] = source

    reports = []
    cited_sources: set[str] = set()
    claim_count_with_valid_citation = 0
    invalid_count = 0

    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError("claims entries must be objects")
        claim_text = claim.get("text")
        if not isinstance(claim_text, str) or not claim_text.strip() or len(claim_text) > 4000:
            raise ValueError("claim text must contain 1 to 4000 characters")
        citations = claim.get("citations", [])
        if not isinstance(citations, list) or len(citations) > MAX_CITATIONS_PER_CLAIM:
            raise ValueError("citations must be a list of at most 20 entries")

        citation_reports = []
        claim_valid = bool(citations)
        for citation in citations:
            if not isinstance(citation, dict):
                raise ValueError("citation entries must be objects")
            sid = citation.get("source_id")
            if not isinstance(sid, str) or not sid.strip():
                raise ValueError("each citation requires source_id")
            sid = sid.strip()
            source = sources.get(sid)
            if source is None:
                citation_reports.append({
                    "source_id": sid, "status": "unknown_source_id",
                    "source_text_match": False,
                })
                claim_valid = False
                continue

            cited_sources.add(sid)
            excerpt = citation.get("excerpt", "")
            if not isinstance(excerpt, str) or len(excerpt) > MAX_EXCERPT_CHARS:
                raise ValueError("citation excerpt must be a string up to 1200 characters")
            source_text = source.get("excerpt") or source.get("text") or source.get("content")
            has_source_text = isinstance(source_text, str) and bool(source_text.strip())
            exact_match = bool(excerpt.strip()) and has_source_text and excerpt.strip() in source_text
            status = "exact_excerpt_match" if exact_match else (
                "source_text_unavailable" if not has_source_text else "excerpt_not_found"
            )
            if not exact_match:
                claim_valid = False
            citation_reports.append({
                "source_id": sid,
                "source_title": source.get("title") if isinstance(source.get("title"), str) else None,
                "source_url": source.get("url") if isinstance(source.get("url"), str) else None,
                "excerpt": excerpt.strip(),
                "status": status,
                "source_text_match": exact_match,
            })

        if claim_valid:
            claim_count_with_valid_citation += 1
        else:
            invalid_count += 1
        reports.append({
            "claim_index": idx,
            "claim_text": claim_text.strip(),
            "citation_count": len(citations),
            "citation_status": "all_citations_matched_source_text" if claim_valid else "needs_citation_review",
            "citations": citation_reports,
        })

    return {
        "audit_type": "source_text_citation_coverage",
        "status": "passed" if claims and invalid_count == 0 else "needs_review",
        "metrics": {
            "claim_count": len(claims),
            "claim_citation_coverage": round(claim_count_with_valid_citation / len(claims), 4) if claims else None,
            "claims_without_valid_citations": invalid_count,
            "unique_sources_cited": len(cited_sources),
        },
        "claims": reports,
        "limitations": [
            "Exact excerpt matching checks traceability to supplied text only.",
            "Source authenticity, freshness, claim entailment, context sufficiency, and factual truth are not verified.",
            "A citation match must not be interpreted as proof that a source supports the claim.",
        ],
    }
