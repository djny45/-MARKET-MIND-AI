"""Evidence-limited comparison utilities for specialist AI agent council outputs.

This module deliberately avoids semantic consensus claims: free-form model summaries
are not sufficient evidence to infer agreement or disagreement.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any


def review_council_outputs(council_result: dict[str, Any]) -> dict[str, Any]:
    """Return reproducible output fingerprints and availability diagnostics."""
    if not isinstance(council_result, dict):
        raise ValueError("council_result must be an object")
    members = council_result.get("members")
    if not isinstance(members, list) or len(members) > 8:
        raise ValueError("members must be a list containing at most 8 council members")

    reviewed = []
    fingerprints = Counter()
    for member in members:
        if not isinstance(member, dict):
            raise ValueError("each member must be an object")
        agent_id = member.get("agent_id")
        status = member.get("status", "unknown")
        analysis = member.get("analysis")
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("each member must have a non-empty agent_id")
        if analysis is not None and not isinstance(analysis, str):
            raise ValueError("analysis must be a string or null")
        normalized = re.sub(r"\\s+", " ", analysis.strip()).casefold() if analysis else ""
        fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None
        if fingerprint:
            fingerprints[fingerprint] += 1
        reviewed.append({
            "agent_id": agent_id,
            "status": status,
            "has_analysis": bool(normalized),
            "analysis_sha256": fingerprint,
        })

    completed = sum(item["has_analysis"] for item in reviewed)
    duplicate_groups = [
        {"analysis_sha256": fingerprint, "member_count": count}
        for fingerprint, count in sorted(fingerprints.items())
        if count > 1
    ]
    unique_analyses = len(fingerprints)
    return {
        "member_count": len(reviewed),
        "member_count_with_analysis": completed,
        "member_count_without_analysis": len(reviewed) - completed,
        "unique_analysis_fingerprints": unique_analyses,
        "identical_output_groups": duplicate_groups,
        "members": reviewed,
        "interpretation": (
            "Exact normalized text fingerprints only. Similarity, factual agreement, "
            "disagreement, and consensus are not inferred from free-form summaries."
        ),
        "consensus": None,
        "research_only": True,
        "paper_trading": False,
        "broker_execution": False,
    }
