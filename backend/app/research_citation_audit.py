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
            normalized_excerpt = excerpt.strip()
            exact_match = bool(normalized_excerpt) and has_source_text and normalized_excerpt in source_text
            status = "exact_excerpt_match" if exact_match else (
                "source_text_unavailable" if not has_source_text else "excerpt_not_found"
            )

            # Optional chunk provenance fields are checked when present. Older
            # citation records remain supported, but cannot claim chunk verification.
            provenance_fields = (
                "source_sha256", "chunk_sha256", "chunk_text", "chunk_index",
                "source_start_char", "source_end_char",
                "excerpt_start_char", "excerpt_end_char",
            )
            has_chunk_provenance = any(field in citation for field in provenance_fields)
            provenance_status = "not_provided"
            if has_chunk_provenance:
                import hashlib
                expected_source_hash = citation.get("source_sha256")
                actual_source_hash = (
                    hashlib.sha256(source_text.encode("utf-8")).hexdigest()
                    if has_source_text else None
                )
                chunk_hash = citation.get("chunk_sha256")
                chunk_text = citation.get("chunk_text")
                chunk_index = citation.get("chunk_index")
                chunk_start = citation.get("source_start_char")
                chunk_end = citation.get("source_end_char")
                start = citation.get("excerpt_start_char")
                end = citation.get("excerpt_end_char")
                valid_offsets = (
                    isinstance(start, int) and not isinstance(start, bool)
                    and isinstance(end, int) and not isinstance(end, bool)
                    and start >= 0 and end >= start
                    and end - start == len(normalized_excerpt)
                )
                offsets_match = (
                    valid_offsets and has_source_text
                    and source_text[start:end] == normalized_excerpt
                )
                hash_matches = (
                    isinstance(expected_source_hash, str)
                    and expected_source_hash.lower() == actual_source_hash
                )
                chunk_index_valid = (
                    isinstance(chunk_index, int)
                    and not isinstance(chunk_index, bool)
                    and chunk_index >= 0
                )
                chunk_hash_valid = (
                    isinstance(chunk_text, str)
                    and isinstance(chunk_hash, str)
                    and hashlib.sha256(chunk_text.encode("utf-8")).hexdigest() == chunk_hash.lower()
                )
                chunk_source_slice_valid = (
                    isinstance(chunk_start, int) and not isinstance(chunk_start, bool)
                    and isinstance(chunk_end, int) and not isinstance(chunk_end, bool)
                    and chunk_start >= 0 and chunk_end >= chunk_start
                    and chunk_end - chunk_start == len(chunk_text or "")
                    and has_source_text and source_text[chunk_start:chunk_end] == chunk_text
                )
                excerpt_inside_chunk = (
                    chunk_source_slice_valid and valid_offsets
                    and chunk_start <= start <= end <= chunk_end
                    and chunk_text[start - chunk_start:end - chunk_start] == normalized_excerpt
                )
                provenance_ok = (
                    hash_matches and chunk_index_valid and offsets_match
                    and chunk_hash_valid and chunk_source_slice_valid
                    and excerpt_inside_chunk
                )
                provenance_status = "verified_source_hash_and_excerpt_offsets" if provenance_ok else "provenance_mismatch"
                if not provenance_ok:
                    exact_match = False
                    status = "provenance_mismatch"
            if not exact_match:
                claim_valid = False
            citation_reports.append({
                "source_id": sid,
                "source_title": source.get("title") if isinstance(source.get("title"), str) else None,
                "source_url": source.get("url") if isinstance(source.get("url"), str) else None,
                "excerpt": normalized_excerpt,
                "status": status,
                "source_text_match": exact_match,
                "chunk_provenance_status": provenance_status,
                "chunk_provenance_verified": provenance_status == "verified_source_hash_and_excerpt_offsets",
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
