"""Build exact citation records from deterministic source chunks.

This helper links a supplied claim to a specific chunk in a previously generated
chunk manifest. It never invents claim text, paraphrases source material, or
asserts that the excerpt semantically supports the claim.
"""
from __future__ import annotations

import hashlib
from typing import Any


def build_chunk_citation(*, source_id: str, manifest: dict[str, Any],
                         chunk_index: int, excerpt: str) -> dict[str, Any]:
    """Return citation metadata only after validating manifest and exact excerpt."""
    if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 200:
        raise ValueError("source_id must be a non-empty string up to 200 characters")
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    source_hash = manifest.get("source_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("manifest source_sha256 must be a SHA-256 hex digest")
    if any(ch not in "0123456789abcdefABCDEF" for ch in source_hash):
        raise ValueError("manifest source_sha256 must be hexadecimal")
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or not chunks or len(chunks) > 100:
        raise ValueError("manifest must contain 1 to 100 chunks")
    if isinstance(chunk_index, bool) or not isinstance(chunk_index, int) or not 0 <= chunk_index < len(chunks):
        raise ValueError("chunk_index is outside the manifest")
    if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 1200:
        raise ValueError("excerpt must contain 1 to 1200 characters")

    chunk = chunks[chunk_index]
    if not isinstance(chunk, dict) or chunk.get("index") != chunk_index:
        raise ValueError("chunk index metadata does not match manifest position")
    text = chunk.get("text")
    chunk_hash = chunk.get("sha256")
    if not isinstance(text, str) or not isinstance(chunk_hash, str):
        raise ValueError("chunk text or hash is missing")
    actual_chunk_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual_chunk_hash != chunk_hash.lower():
        raise ValueError("chunk text hash does not match manifest")
    if chunk.get("source_sha256") != source_hash:
        raise ValueError("chunk source hash does not match manifest")
    start, end = chunk.get("start_char"), chunk.get("end_char")
    if (isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or start < 0 or end < start or end - start != len(text)):
        raise ValueError("chunk source offsets are invalid")
    normalized_excerpt = excerpt.strip()
    if normalized_excerpt not in text:
        raise ValueError("excerpt is not an exact substring of the selected chunk")

    return {
        "source_id": source_id.strip(),
        "excerpt": normalized_excerpt,
        "chunk_index": chunk_index,
        "chunk_sha256": actual_chunk_hash,
        "source_sha256": source_hash.lower(),
        "source_start_char": start,
        "source_end_char": end,
        "excerpt_match": "exact",
        "semantic_support_verified": False,
        "human_review_required": True,
    }
