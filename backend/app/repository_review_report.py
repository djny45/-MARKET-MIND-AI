"""Static repository architecture/dependency summary from bounded review inputs.

Parsing is data-only: no package installation, import of candidate code, or script
execution. Results are inventory hints, not security or license approval.
"""
from __future__ import annotations

import json
import re
import tomllib
from typing import Any

from .github_repository_files import fetch_review_files
from .github_repository_tree import scan_repository_tree
from .github_repository_crawler import GitHubCrawlerError


def _parse_requirement_lines(text: str, source: str) -> list[dict[str, str]]:
    found = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        # Strip inline comments conservatively; preserve markers and extras.
        line = line.split(" #", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
        if name:
            found.append({"name": name, "specifier": line[len(name):].strip(),
                          "source_file": source, "line": str(line_no)})
    return found


def _parse_dependencies(path: str, content: str) -> list[dict[str, str]]:
    lower = path.lower()
    if lower.endswith("requirements.txt"):
        return _parse_requirement_lines(content, path)
    if lower.endswith("pyproject.toml"):
        try:
            data = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, ValueError):
            return [{"name": "(manifest parse error)", "specifier": "",
                     "source_file": path, "line": "1"}]
        deps: list[dict[str, str]] = []
        project = data.get("project", {})
        if isinstance(project, dict) and isinstance(project.get("dependencies"), list):
            deps.extend(_parse_requirement_lines("\n".join(project["dependencies"]), path))
        poetry = data.get("tool", {}).get("poetry", {})
        if isinstance(poetry, dict) and isinstance(poetry.get("dependencies"), dict):
            for name, spec in poetry["dependencies"].items():
                if name.lower() == "python":
                    continue
                deps.append({"name": name, "specifier": str(spec), "source_file": path,
                            "line": "poetry.dependencies"})
        return deps
    if lower.endswith("package.json"):
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return [{"name": "(manifest parse error)", "specifier": "",
                     "source_file": path, "line": "1"}]
        deps = []
        for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            values = data.get(section, {})
            if isinstance(values, dict):
                for name, spec in values.items():
                    deps.append({"name": str(name), "specifier": str(spec),
                                "source_file": path, "line": section})
        return deps
    # Other manifest types are inventoried but not parsed in this initial version.
    return []


def build_repository_review_report(repository_url: str) -> dict[str, Any]:
    tree = scan_repository_tree(repository_url)
    files = fetch_review_files(repository_url)
    if tree["pinned_commit_sha"] != files["pinned_commit_sha"]:
        raise GitHubCrawlerError("Repository HEAD changed between inventory and review retrieval.")
    languages: dict[str, int] = {}
    source_count = 0
    for entry in tree["entries"]:
        language = entry.get("language")
        if entry.get("category") == "source":
            source_count += 1
        if language:
            languages[language] = languages.get(language, 0) + 1

    dependencies = []
    readme_headings = []
    license_evidence = []
    retrieved = {item["path"]: item for item in files["files"]}
    for path, item in retrieved.items():
        if item.get("status") != "retrieved":
            continue
        content = item.get("content", "")
        dependencies.extend(_parse_dependencies(path, content))
        if path.rsplit("/", 1)[-1].lower().startswith("readme"):
            readme_headings.extend(
                {"file": path, "heading": line.strip().lstrip("#").strip()}
                for line in content.splitlines()
                if re.match(r"^#{1,6}\s+\S", line.strip())
            )
        if path.rsplit("/", 1)[-1].lower().startswith(("license", "licence", "notice", "copying")):
            license_evidence.append({
                "path": path, "sha256": item.get("sha256"),
                "content_retrieved": True, "reviewed_or_approved": False,
            })

    manifests = sorted({
        entry["path"] for entry in tree["entries"]
        if entry.get("category") == "dependency_manifest"
    })
    return {
        "schema_version": 1,
        "source_url": tree["source_url"],
        "pinned_commit_sha": tree["pinned_commit_sha"],
        "summary": {
            "tree_entry_count": tree["entry_count"],
            "source_file_count": source_count,
            "language_file_counts": dict(sorted(languages.items())),
            "dependency_manifest_count": len(manifests),
            "parsed_dependency_count": len(dependencies),
            "readme_heading_count": len(readme_headings),
            "license_notice_file_count": len(license_evidence),
        },
        "dependency_manifests": manifests,
        "dependencies": dependencies[:1000],
        "readme_headings": readme_headings[:200],
        "license_notice_evidence": license_evidence,
        "analysis_policy": {
            "static_metadata_and_allowlisted_text_only": True,
            "source_code_semantically_analyzed": False,
            "dependency_installation_or_execution": False,
            "license_approved": False,
            "security_review_complete": False,
            "human_review_required": True,
        },
    }
