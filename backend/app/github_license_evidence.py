"""Retrieve a root-level license file from a pinned public GitHub commit.

This gathers evidence for human review; it does not interpret license terms or
make a legal conclusion. Repository-level SPDX metadata is not accepted as proof.
"""
from __future__ import annotations

import base64
import re
from urllib.parse import quote

from .github_pinned_extraction import _get_json, _REPO, _SHA, _API

_LICENSE_NAMES = {
    "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENSE.rst",
    "COPYING", "COPYING.md", "COPYING.txt",
}
_MAX_LICENSE_BYTES = 30_000


def fetch_pinned_license_evidence(*, repository_url: str, commit_sha: str) -> dict:
    """Fetch a recognized root license file and return unverified evidence."""
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
    sha = commit_sha.lower()

    commit = _get_json(f"{_API}/repos/{owner}/{name}/commits/{sha}")
    if not isinstance(commit, dict) or str(commit.get("sha", "")).lower() != sha:
        raise ValueError("GitHub commit response did not match the requested pinned SHA")

    root = _get_json(f"{_API}/repos/{owner}/{name}/contents/?ref={sha}")
    if not isinstance(root, list):
        raise ValueError("GitHub root directory listing was not a supported response")
    matches = [
        item for item in root
        if isinstance(item, dict)
        and item.get("type") == "file"
        and isinstance(item.get("name"), str)
        and item["name"].upper() in _LICENSE_NAMES
    ]
    if not matches:
        return {
            "repository_url": f"https://github.com/{owner}/{name}",
            "commit_sha": sha,
            "license_file_found": False,
            "license_file_path": None,
            "license_text": None,
            "license_evidence_status": "not_found_at_pinned_root",
            "human_review_required": True,
            "legal_conclusion": False,
            "note": "No recognized root-level license file was found; inspect the pinned tree manually.",
        }
    # Prefer LICENSE over COPYING and choose deterministically if several exist.
    matches.sort(key=lambda item: (item["name"].upper() != "LICENSE", item["name"].lower()))
    item = matches[0]
    path = item["name"]
    if not isinstance(item.get("size"), int) or item["size"] < 0 or item["size"] > _MAX_LICENSE_BYTES:
        raise ValueError("pinned license file exceeds the 30000-byte evidence limit")
    encoded_path = quote(path, safe="")
    file_item = _get_json(f"{_API}/repos/{owner}/{name}/contents/{encoded_path}?ref={sha}")
    if (not isinstance(file_item, dict) or file_item.get("type") != "file"
            or file_item.get("encoding") != "base64"
            or not isinstance(file_item.get("content"), str)):
        raise ValueError("GitHub did not return supported pinned license file content")
    try:
        raw = base64.b64decode(file_item["content"], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("GitHub returned invalid base64 license evidence") from exc
    if len(raw) > _MAX_LICENSE_BYTES or len(raw) != item["size"]:
        raise ValueError("license file size did not match metadata or evidence limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("license evidence is not UTF-8 text") from exc
    if "\x00" in text:
        raise ValueError("binary license evidence is not accepted")
    import hashlib
    return {
        "repository_url": f"https://github.com/{owner}/{name}",
        "commit_sha": sha,
        "license_file_found": True,
        "license_file_path": path,
        "license_file_sha256": hashlib.sha256(raw).hexdigest(),
        "license_text": text,
        "license_evidence_status": "license_file_found_pending_human_review",
        "human_review_required": True,
        "legal_conclusion": False,
        "note": "Exact pinned license text retrieved for review; no legal interpretation or compatibility determination performed.",
    }
