"""Transparent metadata completeness scoring for open-source research evidence.

The score measures presence/consistency of provenance fields only. It does not
assess factual correctness, license compatibility, source quality, or fitness
for skill promotion.
"""
from __future__ import annotations

from typing import Any
import re


def score_source_evidence(candidate: dict[str, Any], license_evidence: dict[str, Any] | None = None) -> dict:
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    license_evidence = license_evidence or {}
    checks = [
        ("repository_url_valid", isinstance(candidate.get("repository_url"), str) and re.fullmatch(r"https://github\.com/[^/\s]+/[^/\s]+", candidate["repository_url"]) is not None, 10),
        ("full_commit_sha_valid", isinstance(candidate.get("commit_sha"), str)
         and re.fullmatch(r"[0-9a-fA-F]{40}", candidate["commit_sha"]) is not None, 20),
        ("file_path_present", bool(candidate.get("file_path")), 10),
        ("source_content_present", isinstance(candidate.get("content"), str)
         and bool(candidate["content"].strip()), 15),
        ("source_sha256_valid", isinstance(candidate.get("content_sha256"), str)
         and re.fullmatch(r"[0-9a-fA-F]{64}", candidate["content_sha256"]) is not None, 15),
        ("pinned_license_file_evidence", license_evidence.get("license_file_found") is True
         and license_evidence.get("commit_sha") == candidate.get("commit_sha")
         and license_evidence.get("repository_url") == candidate.get("repository_url"), 20),
        ("source_is_review_pending", candidate.get("review_required") is True
         or candidate.get("review_status") == "pending", 10),
    ]
    details = [
        {"check": name, "passed": bool(passed), "points": points if passed else 0,
         "max_points": points}
        for name, passed, points in checks
    ]
    total = sum(item["points"] for item in details)
    return {
        "score": total,
        "max_score": sum(item["max_points"] for item in details),
        "checks": details,
        "score_type": "provenance_completeness_heuristic",
        "interpretation": "Completeness indicator only; not a factual, legal, or promotion assessment.",
        "human_review_required": True,
        "automatic_promotion": False,
        "execution_allowed": False,
    }
