"""Safe, provenance-first intake records for open-source research material.

This module records source metadata and a bounded text snapshot for review.
It never executes, imports, or automatically promotes third-party code.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

_ALLOWED_LICENSES = {
    "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT", "MPL-2.0",
}
_GITHUB_REPO = re.compile(r"^https://github\\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\\.git)?/?$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
_MAX_CONTENT_BYTES = 50_000
_MAX_PATH = 500


def _required_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a non-empty string of at most {maximum} characters")
    return value.strip()


def build_source_candidate(
    *,
    repository_url: str,
    commit_sha: str,
    file_path: str,
    license_spdx: str,
    content: str,
    source_kind: str = "documentation",
) -> dict:
    """Create a review-pending source record with immutable provenance.

    Only public GitHub repository URLs and pinned 40-character commit SHAs are
    accepted. A caller must independently verify the license and source content.
    This function does not fetch URLs or validate that the commit exists.
    """
    repository_url = _required_text(repository_url, "repository_url", 300)
    match = _GITHUB_REPO.fullmatch(repository_url)
    parsed = urlparse(repository_url)
    if not match or parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("repository_url must be a canonical public GitHub repository URL")
    owner, repo = match.groups()
    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("repository URL contains an invalid owner or repository")
    canonical_url = f"https://github.com/{owner}/{repo}"

    commit_sha = _required_text(commit_sha, "commit_sha", 40)
    if not _COMMIT.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full 40-character Git commit SHA")

    file_path = _required_text(file_path, "file_path", _MAX_PATH)
    if file_path.startswith("/") or "\\\\" in file_path or any(
        part in {"", ".", ".."} for part in file_path.split("/")
    ):
        raise ValueError("file_path must be a safe repository-relative path")
    if file_path.lower().endswith((".exe", ".dll", ".so", ".dylib", ".bin", ".pyc")):
        raise ValueError("binary or compiled artifacts are not accepted for source intake")

    license_spdx = _required_text(license_spdx, "license_spdx", 50)
    if license_spdx not in _ALLOWED_LICENSES:
        raise ValueError("license is not in the intake allowlist; manual license review is required")

    if source_kind not in {"documentation", "source_excerpt", "research_note"}:
        raise ValueError("source_kind must be documentation, source_excerpt, or research_note")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be non-empty text")
    content_bytes = content.encode("utf-8")
    if len(content_bytes) > _MAX_CONTENT_BYTES:
        raise ValueError("content exceeds the 50000-byte intake limit")
    if "\\x00" in content:
        raise ValueError("content must be plain text, not binary data")

    digest = hashlib.sha256(content_bytes).hexdigest()
    return {
        "record_schema_version": 1,
        "candidate_id": hashlib.sha256(
            f"{canonical_url}@{commit_sha}:{file_path}:{digest}".encode("utf-8")
        ).hexdigest(),
        "repository_url": canonical_url,
        "commit_sha": commit_sha.lower(),
        "file_path": file_path,
        "license_spdx": license_spdx,
        "source_kind": source_kind,
        "content_sha256": digest,
        "content_bytes": len(content_bytes),
        "content": content,
        "review_status": "pending",
        "review_required": True,
        "execution_allowed": False,
        "automatic_copy_allowed": False,
        "automatic_promotion_allowed": False,
        "license_verified_by_caller": True,
        "note": (
            "Metadata and text snapshot only. Caller must verify source URL, commit, "
            "license, attribution, and applicable license obligations before reuse."
        ),
    }
