"""Fetch one bounded text file from a pinned public GitHub commit.

This is deliberately a narrow extractor: fixed GitHub API host, strict repository
and path validation, commit pinning, byte limits, no redirect following, and no
execution. The supplied SPDX identifier remains a caller assertion until review.
"""
from __future__ import annotations

import base64
import re
import httpx

from .open_source_intake import build_source_candidate

_API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(7.0, connect=3.0)
_MAX_BYTES = 50_000
_REPO = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_USER_AGENT = "MARKET-MIND-AI-pinned-source-extractor/1.0"


def _get_json(url: str):
    try:
        response = httpx.get(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
            follow_redirects=False,
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError("GitHub pinned source fetch timed out") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 403 or status == 429:
            raise RuntimeError("GitHub API rate limit or access restriction reached") from exc
        if status == 404:
            raise ValueError("GitHub repository, commit, or file was not found") from exc
        raise RuntimeError(f"GitHub pinned source fetch failed with HTTP {status}") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise RuntimeError("GitHub pinned source fetch could not be completed") from exc


def fetch_pinned_text_candidate(
    *, repository_url: str, commit_sha: str, file_path: str,
    license_spdx: str, source_kind: str = "documentation",
) -> dict:
    """Fetch a text file at an exact commit and return a review-pending candidate."""
    if not isinstance(repository_url, str) or len(repository_url) > 300:
        raise ValueError("repository_url must be a valid public GitHub repository URL")
    match = _REPO.fullmatch(repository_url.strip())
    if not match:
        raise ValueError("repository_url must be a public GitHub repository URL")
    owner, name = match.groups()
    if owner in {".", ".."} or name in {".", ".."}:
        raise ValueError("invalid repository owner or name")
    if not isinstance(commit_sha, str) or not _SHA.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full 40-character Git commit SHA")
    if not isinstance(file_path, str) or not file_path.strip() or len(file_path) > 500:
        raise ValueError("file_path must be a non-empty repository-relative path")
    path = file_path.strip()
    if path.startswith("/") or "\\" in path or any(p in {"", ".", ".."} for p in path.split("/")):
        raise ValueError("file_path must be a safe repository-relative path")

    canonical_repo = f"https://github.com/{owner}/{name}"
    commit = _get_json(f"{_API}/repos/{owner}/{name}/commits/{commit_sha.lower()}")
    if not isinstance(commit, dict) or str(commit.get("sha", "")).lower() != commit_sha.lower():
        raise ValueError("GitHub commit response did not match the requested pinned SHA")

    # GitHub's contents endpoint encodes files as base64. URL-quote path segments
    # independently to avoid path traversal or query injection.
    from urllib.parse import quote
    encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
    item = _get_json(f"{_API}/repos/{owner}/{name}/contents/{encoded_path}?ref={commit_sha.lower()}")
    if not isinstance(item, dict) or item.get("type") != "file":
        raise ValueError("Only regular repository files can be extracted")
    size = item.get("size")
    if not isinstance(size, int) or size < 0 or size > _MAX_BYTES:
        raise ValueError("source file exceeds the 50000-byte extraction limit")
    if item.get("encoding") != "base64" or not isinstance(item.get("content"), str):
        raise ValueError("GitHub did not return a supported base64 text file")
    try:
        raw = base64.b64decode(item["content"], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("GitHub returned invalid base64 file content") from exc
    if len(raw) > _MAX_BYTES or len(raw) != size:
        raise ValueError("source file size did not match the GitHub metadata or limit")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source file is not UTF-8 text") from exc
    if "\x00" in content:
        raise ValueError("binary content is not accepted")

    return build_source_candidate(
        repository_url=canonical_repo, commit_sha=commit_sha.lower(),
        file_path=path, license_spdx=license_spdx, content=content,
        source_kind=source_kind,
    )
