"""Bounded, metadata-only GitHub repository crawler.

This adapter fetches public GitHub REST metadata and a pinned commit record.
It never downloads repository source archives, clones, or executes code.
"""
from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from .open_source_intake import normalize_github_repository_url


API_ROOT = "https://api.github.com"
MAX_RESPONSE_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 8.0
USER_AGENT = "MARKET-MIND-AI-Research/0.1"


class GitHubCrawlerError(RuntimeError):
    """Raised when public GitHub metadata cannot be safely retrieved."""


def _read_bounded_json(response: httpx.Response, *, max_bytes: int = MAX_RESPONSE_BYTES) -> dict:
    response.raise_for_status()
    declared_length = response.headers.get("content-length")
    if declared_length:
        try:
            if int(declared_length) > max_bytes:
                raise GitHubCrawlerError("GitHub API response exceeds the size limit.")
        except ValueError as exc:
            raise GitHubCrawlerError("GitHub API returned an invalid Content-Length.") from exc
    chunks = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise GitHubCrawlerError("GitHub API response exceeds the size limit.")
        chunks.append(chunk)
    try:
        payload = json.loads(b"".join(chunks))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubCrawlerError("GitHub API returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise GitHubCrawlerError("GitHub API response must be a JSON object.")
    return payload


def fetch_repository_metadata(repository_url: str, *, client: httpx.Client | None = None) -> dict:
    """Fetch repository metadata and its current default-branch commit.

    Redirects are disabled to prevent a validated GitHub URL from being used
    as a redirect trampoline. The API host is fixed in code and the URL input
    is reduced to validated owner/repository path segments.
    """
    canonical = normalize_github_repository_url(repository_url)
    owner, repository = canonical.removeprefix("https://github.com/").split("/")
    repo_path = f"{quote(owner, safe='')}/{quote(repository, safe='')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    owns_client = client is None
    session = client or httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        follow_redirects=False,
        headers=headers,
    )
    try:
        repo_response = session.get(f"{API_ROOT}/repos/{repo_path}", headers=headers)
        metadata = _read_bounded_json(repo_response)
        default_branch = metadata.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch.strip():
            raise GitHubCrawlerError("Repository metadata has no valid default branch.")
        branch_path = quote(default_branch, safe="")
        commit_response = session.get(
            f"{API_ROOT}/repos/{repo_path}/commits/{branch_path}",
            headers=headers,
        )
        commit = _read_bounded_json(commit_response)
        sha = commit.get("sha")
        if not isinstance(sha, str) or len(sha) not in (40, 64) or any(
            char not in "0123456789abcdefABCDEF" for char in sha
        ):
            raise GitHubCrawlerError("GitHub API returned an invalid commit SHA.")
        license_data = metadata.get("license")
        license_spdx = license_data.get("spdx_id") if isinstance(license_data, dict) else None
        return {
            "schema_version": 1,
            "source_url": canonical,
            "api_source": API_ROOT,
            "repository": {
                "full_name": metadata.get("full_name"),
                "description": metadata.get("description"),
                "default_branch": default_branch,
                "visibility": metadata.get("visibility"),
                "archived": metadata.get("archived"),
                "license_spdx_id": license_spdx,
            },
            "pinned_commit": {
                "sha": sha.lower(),
                "commit_url": commit.get("html_url"),
                "committed_at": (commit.get("commit") or {}).get("committer", {}).get("date")
                if isinstance(commit.get("commit"), dict)
                and isinstance((commit.get("commit") or {}).get("committer"), dict)
                else None,
            },
            "crawler_policy": {
                "metadata_only": True,
                "redirects_followed": False,
                "source_archive_downloaded": False,
                "code_executed": False,
            },
        }
    except httpx.HTTPError as exc:
        raise GitHubCrawlerError(f"GitHub metadata request failed: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            session.close()
