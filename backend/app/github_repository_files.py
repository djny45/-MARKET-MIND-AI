"""Bounded retrieval of allowlisted documentation and manifest files at a pinned SHA.

This module deliberately excludes arbitrary source files and never executes,
installs, or imports retrieved repository content.
"""
from __future__ import annotations

import base64
import hashlib
from urllib.parse import quote

import httpx

from .github_repository_crawler import (
    API_ROOT,
    GitHubCrawlerError,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    _read_bounded_json,
    fetch_repository_metadata,
)
from .github_repository_tree import scan_repository_tree
from .open_source_intake import normalize_github_repository_url

MAX_FILE_BYTES = 64_000
MAX_TOTAL_BYTES = 256_000
MAX_FILES = 12
MAX_CONTENTS_RESPONSE_BYTES = 512_000

ALLOWLIST_NAMES = {
    "readme", "readme.md", "readme.rst", "readme.txt",
    "license", "license.md", "license.txt", "license.rst",
    "licence", "licence.md", "licence.txt",
    "notice", "notice.md", "notice.txt", "copying",
    "requirements.txt", "pyproject.toml", "poetry.lock",
    "pipfile", "pipfile.lock", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "cargo.toml", "cargo.lock",
    "go.mod", "go.sum", "pom.xml", "build.gradle",
    "build.gradle.kts", "gemfile", "gemfile.lock",
    "composer.json", "composer.lock",
}


def _is_allowlisted(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return name in ALLOWLIST_NAMES


def _decode_contents(payload: dict, *, expected_path: str) -> bytes:
    if payload.get("path") != expected_path:
        raise GitHubCrawlerError("GitHub Contents API returned a mismatched path.")
    if payload.get("encoding") != "base64":
        raise GitHubCrawlerError("GitHub Contents API returned an unsupported encoding.")
    encoded = payload.get("content")
    if not isinstance(encoded, str):
        raise GitHubCrawlerError("GitHub Contents API returned no file content.")
    try:
        raw = base64.b64decode("".join(encoded.split()), validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise GitHubCrawlerError("GitHub Contents API returned invalid base64.") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise GitHubCrawlerError("Repository file exceeds the per-file size limit.")
    return raw


def fetch_review_files(repository_url: str, *, client: httpx.Client | None = None) -> dict:
    """Fetch only README/license/dependency allowlist files at the pinned SHA."""
    canonical = normalize_github_repository_url(repository_url)
    # Pin first; tree results and contents requests must refer to the same immutable SHA.
    metadata = fetch_repository_metadata(canonical, client=client)
    pinned_sha = metadata["pinned_commit"]["sha"]
    tree = scan_repository_tree(canonical, client=client)
    if tree["pinned_commit_sha"] != pinned_sha:
        raise GitHubCrawlerError("Repository HEAD changed during scan; retry against a pinned commit.")
    candidates = [
        item["path"] for item in tree["entries"]
        if item.get("type") == "blob"
        and item.get("size") is not None
        and item["size"] <= MAX_FILE_BYTES
        and _is_allowlisted(item["path"])
    ]
    # Prioritize README, license/notice, then dependency manifests.
    def priority(path: str) -> tuple[int, str]:
        name = path.rsplit("/", 1)[-1].lower()
        if name.startswith("readme"):
            group = 0
        elif name.startswith(("license", "licence", "notice", "copying")):
            group = 1
        else:
            group = 2
        return group, path.lower()

    candidates = sorted(set(candidates), key=priority)[:MAX_FILES]
    owner, repo = canonical.removeprefix("https://github.com/").split("/")
    repo_path = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
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
    files = []
    total_bytes = 0
    try:
        for path in candidates:
            if total_bytes >= MAX_TOTAL_BYTES:
                break
            encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
            response = session.get(
                f"{API_ROOT}/repos/{repo_path}/contents/{encoded_path}?ref={quote(pinned_sha, safe='')}",
                headers=headers,
            )
            payload = _read_bounded_json(response, max_bytes=MAX_CONTENTS_RESPONSE_BYTES)
            raw = _decode_contents(payload, expected_path=path)
            if total_bytes + len(raw) > MAX_TOTAL_BYTES:
                break
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                files.append({
                    "path": path,
                    "sha": payload.get("sha"),
                    "size_bytes": len(raw),
                    "status": "skipped_non_utf8",
                })
                continue
            files.append({
                "path": path,
                "sha": payload.get("sha"),
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "status": "retrieved",
                "content": text,
            })
            total_bytes += len(raw)
        return {
            "schema_version": 1,
            "source_url": canonical,
            "pinned_commit_sha": pinned_sha,
            "retrieved_file_count": sum(item["status"] == "retrieved" for item in files),
            "total_bytes": total_bytes,
            "files": files,
            "retrieval_policy": {
                "allowlisted_file_names_only": True,
                "max_files": MAX_FILES,
                "max_file_bytes": MAX_FILE_BYTES,
                "max_total_bytes": MAX_TOTAL_BYTES,
                "content_hashes": "sha256",
                "source_code_files_retrieved": False,
                "dependencies_installed": False,
                "repository_code_executed": False,
                "license_review_still_required": True,
                "retrieved_content_is_untrusted": True,
            },
        }
    except httpx.HTTPError as exc:
        raise GitHubCrawlerError(
            f"GitHub file retrieval failed: {type(exc).__name__}"
        ) from exc
    finally:
        if owns_client:
            session.close()
