"""Pinned, metadata-only GitHub repository tree inventory.

The scanner reports paths and file metadata only. It does not fetch source
contents, clone archives, install dependencies, or execute repository code.
"""
from __future__ import annotations

from collections import Counter
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
from .open_source_intake import normalize_github_repository_url

MAX_TREE_RESPONSE_BYTES = 4_000_000
MAX_TREE_ENTRIES = 20_000
MAX_PATH_LENGTH = 500

DEPENDENCY_FILES = {
    "requirements.txt", "pyproject.toml", "poetry.lock", "pipfile",
    "pipfile.lock", "package.json", "package-lock.json", "pnpm-lock.yaml",
    "yarn.lock", "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts", "gemfile", "gemfile.lock",
    "composer.json", "composer.lock",
}
DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
CODE_SUFFIXES = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".c": "C", ".h": "C/C++", ".cpp": "C++", ".cc": "C++",
    ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
}


def _classify_path(path: str) -> dict:
    lower = path.lower()
    basename = lower.rsplit("/", 1)[-1]
    suffix = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""
    if basename in DEPENDENCY_FILES:
        category = "dependency_manifest"
    elif basename.startswith("readme"):
        category = "readme"
    elif basename in {"license", "license.md", "license.txt", "copying", "notice", "notice.md"}:
        category = "license_or_notice"
    elif suffix in DOC_SUFFIXES:
        category = "documentation"
    elif suffix in CODE_SUFFIXES:
        category = "source"
    elif basename.startswith(".github/") or "/.github/" in lower:
        category = "github_configuration"
    else:
        category = "other"
    return {"category": category, "language": CODE_SUFFIXES.get(suffix)}


def scan_repository_tree(repository_url: str, *, client: httpx.Client | None = None) -> dict:
    """Fetch a bounded tree manifest for the immutable commit from metadata."""
    canonical = normalize_github_repository_url(repository_url)
    owns_client = client is None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    session = client or httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        follow_redirects=False,
        headers=headers,
    )
    try:
        metadata = fetch_repository_metadata(canonical, client=session)
        pinned = metadata["pinned_commit"]["sha"]
        owner, repo = canonical.removeprefix("https://github.com/").split("/")
        repo_path = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        response = session.get(
            f"{API_ROOT}/repos/{repo_path}/git/trees/{quote(pinned, safe='')}?recursive=1",
            headers=headers,
        )
        tree_payload = _read_bounded_json(response, max_bytes=MAX_TREE_RESPONSE_BYTES)
        if tree_payload.get("truncated") is True:
            raise GitHubCrawlerError(
                "GitHub tree is truncated; refusing to report an incomplete inventory."
            )
        tree = tree_payload.get("tree")
        if not isinstance(tree, list):
            raise GitHubCrawlerError("GitHub API tree response has no valid tree list.")
        if len(tree) > MAX_TREE_ENTRIES:
            raise GitHubCrawlerError("Repository tree exceeds the entry limit.")
        entries = []
        counts = Counter()
        dependency_files = []
        docs = []
        for item in tree:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            kind = item.get("type")
            if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH:
                continue
            if kind not in {"blob", "tree", "commit"}:
                continue
            # Git submodules are recorded as references only; never traversed.
            classification = _classify_path(path) if kind == "blob" else {
                "category": "directory", "language": None
            }
            entry = {
                "path": path,
                "type": kind,
                "sha": item.get("sha"),
                "size": item.get("size") if kind == "blob" else None,
                **classification,
            }
            entries.append(entry)
            counts[classification["category"]] += 1
            if classification["category"] == "dependency_manifest":
                dependency_files.append(path)
            if classification["category"] in {"readme", "documentation"}:
                docs.append(path)
        return {
            "schema_version": 1,
            "source_url": canonical,
            "pinned_commit_sha": pinned,
            "tree_sha": tree_payload.get("sha"),
            "entry_count": len(entries),
            "category_counts": dict(sorted(counts.items())),
            "dependency_manifests": sorted(dependency_files),
            "documentation_paths": sorted(docs)[:200],
            "entries": entries,
            "scanner_policy": {
                "metadata_and_paths_only": True,
                "source_contents_downloaded": False,
                "submodules_traversed": False,
                "dependencies_installed": False,
                "repository_code_executed": False,
                "human_review_required": True,
            },
        }
    except httpx.HTTPError as exc:
        raise GitHubCrawlerError(
            f"GitHub tree request failed: {type(exc).__name__}"
        ) from exc
    finally:
        if owns_client:
            session.close()
