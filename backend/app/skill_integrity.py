"""Deterministic integrity audit for the catalog, reference skills and workers.

This module never executes imported skill content. It only validates files,
metadata and references, and reports activation status.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .skill_catalog import list_skills, load_skill
from .workers import list_workers

REPO_ROOT = Path(__file__).resolve().parents[2]
VIBE_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "vibe-trading" / "skills"


def frontmatter(text: str) -> dict[str, str]:
    """Parse the leading YAML-style frontmatter block without a YAML dependency."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def audit_catalog() -> dict[str, Any]:
    """Validate every allowlisted catalog skill and its activation metadata."""
    skills = list_skills()
    ids = [skill["id"] for skill in skills]
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for skill in skills:
        skill_id = skill["id"]
        if skill_id in seen:
            issues.append({"id": skill_id, "issue": "duplicate_id"})
        seen.add(skill_id)
        if not skill.get("description"):
            issues.append({"id": skill_id, "issue": "missing_description"})
        if not skill.get("available"):
            issues.append({"id": skill_id, "issue": "unavailable"})
        if skill.get("broker_execution"):
            issues.append({"id": skill_id, "issue": "broker_execution_enabled"})
        try:
            loaded = load_skill(skill_id)
        except (KeyError, FileNotFoundError):
            issues.append({"id": skill_id, "issue": "not_loadable"})
            continue
        if not str(loaded.get("content", "")).strip():
            issues.append({"id": skill_id, "issue": "empty_content"})
    return {
        "count": len(skills),
        "ids": ids,
        "issues": issues,
        "activation": "allowlisted_and_loadable",
    }


def audit_reference_skills() -> dict[str, Any]:
    """Validate vendored reference skills without loading or executing them."""
    issues: list[dict[str, str]] = []
    entries: list[dict[str, str]] = []
    if VIBE_SKILL_ROOT.is_dir():
        for folder in sorted(p for p in VIBE_SKILL_ROOT.iterdir() if p.is_dir()):
            skill_file = folder / "SKILL.md"
            if not skill_file.is_file():
                issues.append({"id": folder.name, "issue": "missing_skill_md"})
                continue
            meta = frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
            if not meta.get("name") or not meta.get("description"):
                issues.append({"id": folder.name, "issue": "missing_frontmatter"})
            entries.append({"id": folder.name, "name": meta.get("name", folder.name)})
    names = [entry["name"] for entry in entries]
    for name in sorted({n for n in names if names.count(n) > 1}):
        issues.append({"id": name, "issue": "duplicate_reference_name"})
    return {
        "count": len(entries),
        "entries": entries,
        "issues": issues,
        "activation": "reference_only_not_registered",
    }


def audit_workers() -> dict[str, Any]:
    """Validate worker metadata, identity uniqueness and skill references."""
    workers = list_workers()
    allowed = {skill["id"] for skill in list_skills()}
    issues: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_namespaces: set[str] = set()
    required = ("id", "name", "department", "specialty", "kind", "model", "memory_namespace", "status", "skill_refs")
    for worker in workers:
        wid = str(worker.get("id", ""))
        if wid in seen_ids:
            issues.append({"id": wid, "issue": "duplicate_worker_id"})
        seen_ids.add(wid)
        namespace = str(worker.get("memory_namespace", ""))
        if namespace in seen_namespaces:
            issues.append({"id": wid, "issue": "duplicate_memory_namespace"})
        seen_namespaces.add(namespace)
        for key in required:
            if key not in worker or worker[key] in (None, "", []):
                issues.append({"id": wid, "issue": f"missing_{key}"})
        refs = worker.get("skill_refs") or []
        if not isinstance(refs, list):
            issues.append({"id": wid, "issue": "invalid_skill_refs"})
            continue
        for ref in refs:
            if ref not in allowed:
                issues.append({"id": wid, "issue": f"unresolved_skill_ref:{ref}"})
    return {
        "count": len(workers),
        "departments": len({w.get("department") for w in workers}),
        "issues": issues,
        "activation": "registry_templates_shared_core",
    }


def full_integrity_report() -> dict[str, Any]:
    catalog = audit_catalog()
    reference = audit_reference_skills()
    workers = audit_workers()
    total_issues = len(catalog["issues"]) + len(reference["issues"]) + len(workers["issues"])
    return {
        "catalog_skills": catalog["count"],
        "reference_skills": reference["count"],
        "total_skill_definitions": catalog["count"] + reference["count"],
        "workers": workers["count"],
        "worker_departments": workers["departments"],
        "total_issues": total_issues,
        "catalog_issues": catalog["issues"],
        "reference_issues": reference["issues"],
        "worker_issues": workers["issues"],
        "brokerage_execution": False,
    }
