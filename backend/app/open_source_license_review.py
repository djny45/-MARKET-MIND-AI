"""Human-review checklist for pinned open-source license evidence.

This module deliberately does not interpret license text or grant reuse rights.
It only checks whether evidence is tied to the exact source candidate and emits
an uncompleted checklist for a human reviewer.
"""
from __future__ import annotations

import hashlib


def build_license_review_checklist(candidate: dict, evidence: dict | None) -> dict:
    """Build a review-only checklist; never auto-approve source reuse."""
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a source candidate object")
    required = ("repository_url", "commit_sha", "license_spdx", "content_sha256")
    if any(not isinstance(candidate.get(key), str) or not candidate[key].strip()
           for key in required):
        raise ValueError("candidate is missing required provenance fields")

    evidence_matches = bool(
        isinstance(evidence, dict)
        and evidence.get("repository_url") == candidate["repository_url"]
        and str(evidence.get("commit_sha", "")).lower() == candidate["commit_sha"].lower()
        and evidence.get("license_file_found") is True
        and evidence.get("license_evidence_status") == "license_file_found_pending_human_review"
        and isinstance(evidence.get("license_file_sha256"), str)
        and len(evidence["license_file_sha256"]) == 64
        and isinstance(evidence.get("license_text"), str)
        and bool(evidence["license_text"].strip())
    )
    checklist = [
        {"item": "Verify repository and pinned commit match the intended source",
         "checked": None, "reviewer_note": None},
        {"item": "Read the complete license text and any additional notices",
         "checked": None, "reviewer_note": None},
        {"item": "Confirm attribution, notice, and redistribution obligations",
         "checked": None, "reviewer_note": None},
        {"item": "Confirm license compatibility for the intended use",
         "checked": None, "reviewer_note": None},
        {"item": "Confirm whether modifications or downstream distribution require notices",
         "checked": None, "reviewer_note": None},
    ]
    return {
        "candidate_id": candidate.get("candidate_id"),
        "repository_url": candidate["repository_url"],
        "commit_sha": candidate["commit_sha"].lower(),
        "claimed_spdx": candidate["license_spdx"],
        "evidence_match": evidence_matches,
        "evidence_sha256": evidence.get("license_file_sha256") if evidence_matches else None,
        "evidence_status": "matched_pending_human_review" if evidence_matches else "missing_or_mismatched",
        "checklist": checklist,
        "review_status": "pending_human_review",
        "human_review_required": True,
        "reuse_approved": False,
        "execution_allowed": False,
        "automatic_copy_allowed": False,
        "legal_conclusion": False,
        "warning": "This checklist is not legal advice and does not determine license compatibility or grant permission to reuse.",
    }
