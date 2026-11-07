"""Conservative static compatibility hints for open-source repository review.

This module compares declared dependency names against the current project's
manifest inventory. It is not a resolver, license checker, security audit, or
approval to install/run code.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

# Normalize common Python package naming variants. Do not infer equivalence
# across ecosystems (e.g. npm package name vs PyPI name).
def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def build_compatibility_report(
    candidate_report: dict[str, Any],
    project_dependencies: list[dict[str, str]],
) -> dict[str, Any]:
    """Return explainable name-overlap hints, keeping source manifest provenance."""
    if not isinstance(candidate_report, dict):
        raise TypeError("candidate_report must be a dictionary")
    if not isinstance(project_dependencies, list):
        raise TypeError("project_dependencies must be a list")

    project_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in project_dependencies:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        ecosystem = str(item.get("ecosystem", "python")).strip().lower()
        project_by_name[f"{ecosystem}:{_normalize_name(item['name'])}"].append(item)

    candidate_items = candidate_report.get("dependencies", [])
    if not isinstance(candidate_items, list):
        candidate_items = []

    matches = []
    seen = set()
    for item in candidate_items[:1000]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        ecosystem = str(item.get("ecosystem", "python")).strip().lower()
        normalized = _normalize_name(item["name"])
        key = f"{ecosystem}:{normalized}"
        if not normalized or key in seen:
            continue
        seen.add(key)
        project_matches = project_by_name.get(key, [])
        matches.append({
            "dependency": item["name"],
            "normalized_name": normalized,
            "ecosystem": ecosystem,
            "candidate_manifest": item.get("source_file"),
            "candidate_specifier": item.get("specifier", ""),
            "project_name_match": bool(project_matches),
            "project_matches": [
                {
                    "name": match.get("name"),
                    "specifier": match.get("specifier", ""),
                    "manifest": match.get("source_file"),
                }
                for match in project_matches[:20]
            ],
            "compatibility_status": (
                "name_overlap_requires_version_review"
                if project_matches else "not_found_by_name_only"
            ),
        })

    overlapping = sum(1 for item in matches if item["project_name_match"])
    return {
        "schema_version": 1,
        "candidate_source": candidate_report.get("source_url"),
        "candidate_commit": candidate_report.get("pinned_commit_sha"),
        "dependency_count_evaluated": len(matches),
        "name_overlap_count": overlapping,
        "dependencies": matches,
        "limitations": [
            "Name overlap is not proof of API or runtime compatibility.",
            "Version specifiers are displayed, not resolved against a lockfile.",
            "Transitive dependencies, platform markers, extras, and build constraints are not resolved.",
            "Package names from different ecosystems are never compared.",
            "No packages are downloaded, installed, imported, or executed.",
            "License and security approval are separate human-review gates.",
        ],
        "approval": {
            "compatible": False,
            "install_allowed": False,
            "execution_allowed": False,
            "human_review_required": True,
        },
    }
