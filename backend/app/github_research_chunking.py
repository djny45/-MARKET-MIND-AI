"""Deterministic, bounded chunking for review-pending open-source research text.

Chunks retain exact source offsets and hashes. This is preprocessing only—not
semantic understanding, instruction extraction, or automatic skill promotion.
"""
from __future__ import annotations

import hashlib


def chunk_research_text(
    text: str, *, max_chars: int = 4000, overlap_chars: int = 200,
) -> dict:
    """Split UTF-8 text into deterministic chunks with source offsets and hashes."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text.encode("utf-8")) > 50_000:
        raise ValueError("text exceeds the 50000-byte research chunking limit")
    if (isinstance(max_chars, bool) or not isinstance(max_chars, int)
            or not 200 <= max_chars <= 8000):
        raise ValueError("max_chars must be between 200 and 8000")
    if (isinstance(overlap_chars, bool) or not isinstance(overlap_chars, int)
            or not 0 <= overlap_chars < max_chars // 2):
        raise ValueError("overlap_chars must be non-negative and less than half max_chars")

    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Prefer a nearby newline/space boundary without making tiny chunks.
            floor = start + max_chars // 2
            boundary = max(text.rfind("\n", floor, end), text.rfind(" ", floor, end))
            if boundary > floor:
                end = boundary + 1
        chunk_text = text[start:end]
        chunks.append({
            "index": len(chunks),
            "start_char": start,
            "end_char": end,
            "text": chunk_text,
            "sha256": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            "source_sha256": source_hash,
        })
        if end >= len(text):
            break
        start = end - overlap_chars
    return {
        "source_sha256": source_hash,
        "source_chars": len(text),
        "chunk_count": len(chunks),
        "max_chars": max_chars,
        "overlap_chars": overlap_chars,
        "chunks": chunks,
        "processing_mode": "deterministic_text_chunking",
        "semantic_extraction": False,
        "instruction_injection": False,
        "auto_promotion": False,
    }
