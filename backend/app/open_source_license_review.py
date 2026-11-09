"""Human-review checklist for pinned open-source license evidence.

This module deliberately does not interpret license text or grant reuse rights.
It only checks whether evidence is tied to the exact source candidate and emits
an uncompleted checklist for a human reviewer.
"""
from __future__ import annotations

import hashlib


def _validate_candidate_integrity(candidate: dict) -> None:
    """Validate candidate content hash and deterministic ID when content is present."""
    if "content" not in candidate:
        return  # Metadata-only records may be reviewed, but cannot be integrity-verified here.
    content = candidate.get("content")
    if not isinstance(content, str):
        raise ValueError("candidate content must be text for integrity verification")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != candidate.get("content_sha256"):
        raise ValueError("candidate content digest mismatch")
    expected_id = hashlib.sha256(
        f"{candidate['repository_url']}@{candidate['commit_sha']}:{candidate.get('file_path', '')}:{digest}".encode("utf-8")
    ).hexdigest()
    if candidate.get("candidate_id") != expected_id:
        raise ValueError("candidate identifier mismatch")


def build_license_review_checklist(candidate: dict, evidence: dict | None) -> dict:
    """Build a review-only checklist; never auto-approve source reuse."""
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a source candidate object")
    required = ("repository_url", "commit_sha", "license_spdx", "content_sha256")
    if any(not isinstance(candidate.get(key), str) or not candidate[key].strip()
           for key in required):
        raise ValueError("candidate is missing required provenance fields")
    _validate_candidate_integrity(candidate)

    evidence_text = evidence.get("license_text") if isinstance(evidence, dict) else None
    evidence_digest = evidence.get("license_file_sha256") if isinstance(evidence, dict) else None
    evidence_digest_valid = bool(
        isinstance(evidence_text, str)
        and isinstance(evidence_digest, str)
        and len(evidence_digest) == 64
        and hashlib.sha256(evidence_text.encode("utf-8")).hexdigest() == evidence_digest.lower()
    )
    evidence_matches = bool(
        isinstance(evidence, dict)
        and evidence.get("repository_url") == candidate["repository_url"]
        and str(evidence.get("commit_sha", "")).lower() == candidate["commit_sha"].lower()
        and evidence.get("license_file_found") is True
        and evidence.get("license_evidence_status") == "license_file_found_pending_human_review"
        and evidence_digest_valid
        and isinstance(evidence_text, str)
        and bool(evidence_text.strip())
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
        "evidence_digest_valid": evidence_digest_valid,
        "checklist": checklist,
        "review_status": "pending_human_review",
        "human_review_required": True,
        "reuse_approved": False,
        "execution_allowed": False,
        "automatic_copy_allowed": False,
        "legal_conclusion": False,
        "warning": "This checklist is not legal advice and does not determine license compatibility or grant permission to reuse.",
    }
