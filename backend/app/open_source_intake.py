"""Safe intake planner for open-source repository adaptation.

This module deliberately does not clone, execute, or import third-party code.
It creates a normalized, auditable review record before a future sandboxed
crawler/adapter is allowed to fetch source material.
"""
from __future__ import annotations

from urllib.parse import urlsplit


_ALLOWED_HOST = "github.com"
_REPO_PARTS = 2
_MAX_URL_LENGTH = 2048
_REVIEW_STEPS = [
    "Fetch repository metadata and pinned commit using an allowlisted GitHub API client.",
    "Record repository owner, license identifier, source URL, commit SHA, and retrieval timestamp.",
    "Inspect license text and NOTICE files; unresolved or missing licensing blocks reuse.",
    "Enumerate files without running them; reject secrets, binaries, and unexpected path traversal.",
    "Review dependency manifests, install hooks, scripts, and permissions for supply-chain risk.",
    "Create a minimal patch in an isolated workspace; preserve upstream attribution and license notices.",
    "Run static checks and tests in a restricted sandbox with no credentials or network by default.",
    "Compare behavior against a baseline; require human approval before merging or enabling a skill.",
]


def normalize_github_repository_url(url: str) -> str:
    """Accept only a canonical public GitHub repository URL (owner/repo)."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("repository_url must be a non-empty string")
    url = url.strip()
    if len(url) > _MAX_URL_LENGTH:
        raise ValueError("repository_url exceeds the maximum length")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != _ALLOWED_HOST:
        raise ValueError("only https://github.com/owner/repository URLs are accepted")
    if parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("credentials and custom ports are not accepted")
    if parts.query or parts.fragment:
        raise ValueError("query strings and fragments are not accepted")
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) != _REPO_PARTS:
        raise ValueError("URL must point to exactly owner/repository")
    owner, repository = segments
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository:
        raise ValueError("owner and repository must be non-empty")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    if any(ch not in allowed for ch in owner + repository):
        raise ValueError("owner or repository contains unsupported characters")
    if owner in {".", ".."} or repository in {".", ".."}:
        raise ValueError("invalid owner or repository")
    return f"https://github.com/{owner}/{repository}"


def build_open_source_intake(repository_url: str, *, license_id: str | None = None) -> dict:
    """Return a review-only intake plan; unknown licensing is a hard review gate."""
    canonical_url = normalize_github_repository_url(repository_url)
    normalized_license = license_id.strip() if isinstance(license_id, str) else None
    if normalized_license == "":
        normalized_license = None
    return {
        "schema_version": 1,
        "source_url": canonical_url,
        "license_id": normalized_license,
        "license_status": "identified_needs_text_review" if normalized_license else "unknown_block_reuse",
        "intake_status": "pending_review",
        "reuse_allowed": False,
        "execution_allowed": False,
        "auto_merge_allowed": False,
        "review_steps": list(_REVIEW_STEPS),
        "required_evidence": [
            "pinned_commit_sha",
            "license_and_notice_text",
            "file_manifest",
            "dependency_and_script_review",
            "security_scan_report",
            "test_results",
            "upstream_attribution",
            "human_approval_record",
        ],
        "policy": {
            "no_unreviewed_code_execution": True,
            "no_credential_access": True,
            "no_automatic_license_assumption": True,
            "no_automatic_merge": True,
            "network_disabled_during_tests_by_default": True,
        },
    }
