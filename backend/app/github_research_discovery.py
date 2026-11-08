"""Bounded GitHub repository discovery for open-source research (metadata only).

Uses the fixed GitHub API origin, accepts a short search phrase (not a URL),
and returns a small set of metadata records. It never downloads or executes code.
Discovery results are unverified research leads; license and source content need
separate pinned-commit intake and human review.
"""
from __future__ import annotations

import re
import httpx

_GITHUB_SEARCH = "https://api.github.com/search/repositories"
_USER_AGENT = "MARKET-MIND-AI-research-discovery/1.0"
_MAX_QUERY = 180
_MAX_RESULTS = 10
_TIMEOUT = httpx.Timeout(5.0, connect=2.0)


def discover_github_repositories(query: str, limit: int = 5) -> dict:
    """Search public GitHub repository metadata; no arbitrary URL fetching."""
    if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY:
        raise ValueError("query must be a non-empty string of at most 180 characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULTS:
        raise ValueError("limit must be between 1 and 10")
    # Strip control chars and collapse whitespace before sending to GitHub.
    clean_query = re.sub(r"[\\x00-\\x1f\\x7f]", " ", query)
    clean_query = " ".join(clean_query.split())
    if not clean_query:
        raise ValueError("query must contain searchable text")

    try:
        response = httpx.get(
            _GITHUB_SEARCH,
            params={"q": clean_query, "sort": "stars", "order": "desc", "per_page": limit},
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
            follow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError("GitHub repository search timed out") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 403 or status == 429:
            raise RuntimeError("GitHub API rate limit or access restriction reached") from exc
        raise RuntimeError(f"GitHub repository search failed with HTTP {status}") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise RuntimeError("GitHub repository search could not be completed") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RuntimeError("GitHub API returned an unexpected response shape")

    items = []
    for repo in payload["items"][:limit]:
        if not isinstance(repo, dict):
            continue
        full_name = repo.get("full_name")
        html_url = repo.get("html_url")
        if (not isinstance(full_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name)
                or not isinstance(html_url, str) or not html_url.startswith("https://github.com/")):
            continue
        license_data = repo.get("license")
        license_spdx = license_data.get("spdx_id") if isinstance(license_data, dict) else None
        items.append({
            "full_name": full_name,
            "repository_url": f"https://github.com/{full_name}",
            "description": (repo.get("description") or "")[:500],
            "stars": repo.get("stargazers_count") if isinstance(repo.get("stargazers_count"), int) else None,
            "default_branch": (repo.get("default_branch") or "")[:120],
            "license_spdx": license_spdx if isinstance(license_spdx, str) else None,
            "updated_at": repo.get("updated_at") if isinstance(repo.get("updated_at"), str) else None,
            "source": "GitHub public repository search API",
            "review_status": "discovery_only",
            "source_content_fetched": False,
            "license_verified": False,
            "execution_allowed": False,
            "automatic_copy_allowed": False,
        })
    return {
        "query": clean_query,
        "count": len(items),
        "repositories": items,
        "research_only": True,
        "note": "Metadata discovery only. Verify repository, pinned commit, license terms, and source before intake; no code was fetched or executed.",
    }
