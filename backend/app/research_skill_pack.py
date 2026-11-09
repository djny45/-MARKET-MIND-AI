"""Loader for the versioned 300-skill MARKET-MIND research catalog.

Catalog entries are advisory research procedures, not executable plugins.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PACK_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "market-mind-300-research-skills"
    / "SKILL.md"
)
SKILL_PACK_VERSION = "1.0.0"
SKILL_ID_PREFIX = "mm-skill-"
SKILL_COUNT = 300
_HEADING = re.compile(r"^###\s+(\d{3})\.\s+(.+?)\s*$", re.MULTILINE)
_DOMAIN_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _parse_catalog():
    """Return numbered entries with their source-defined level-two domain."""
    if not SKILL_PACK_PATH.is_file():
        return []
    text = SKILL_PACK_PATH.read_text(encoding="utf-8")
    matches = list(_HEADING.finditer(text))
    domain_headings = list(_DOMAIN_HEADING.finditer(text))
    entries = []
    for index, match in enumerate(matches):
        number = int(match.group(1))
        title = match.group(2).strip()
        domain = next(
            (heading.group(1).strip() for heading in reversed(domain_headings)
             if heading.start() < match.start()),
            None,
        )
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        entries.append({
            "id": f"{SKILL_ID_PREFIX}{number:03d}",
            "name": title,
            "number": number,
            "domain": domain,
            "content": f"### {number:03d}. {title}\n\n{section}",
        })
    return entries


def _display_skill_path():
    """Return a repository-relative path when possible, otherwise a test-safe path."""
    try:
        return str(SKILL_PACK_PATH.relative_to(REPO_ROOT))
    except ValueError:
        return str(SKILL_PACK_PATH)


def list_pack_skills():
    """List skills only when the complete, ordered catalog has valid domains."""
    entries = _parse_catalog()
    expected_ids = [f"{SKILL_ID_PREFIX}{number:03d}" for number in range(1, SKILL_COUNT + 1)]
    if len(entries) != SKILL_COUNT:
        return []
    if [entry["id"] for entry in entries] != expected_ids:
        return []
    if len({entry["name"] for entry in entries}) != SKILL_COUNT:
        return []
    if any(not entry["domain"] for entry in entries):
        return []
    return [
        {
            "id": entry["id"],
            "name": entry["name"],
            "domain": entry["domain"],
            "description": f"Research skill: {entry['name']}.",
            "path": _display_skill_path(),
            "available": True,
            "mode": "research_evaluation_only",
            "requires_external_tools": False,
            "skill_pack_version": SKILL_PACK_VERSION,
        }
        for entry in entries
    ]


def load_pack_skill(skill_id):
    """Load exactly one validated skill section by its stable ID."""
    entries = list_pack_skills()
    entry = next((item for item in entries if item["id"] == skill_id), None)
    if entry is None:
        raise KeyError(skill_id)
    parsed = next(item for item in _parse_catalog() if item["id"] == skill_id)
    return {
        "id": skill_id,
        "name": parsed["name"],
        "domain": parsed["domain"],
        "description": f"Research skill: {parsed['name']}.",
        "content": parsed["content"],
        "mode": "research_evaluation_only",
        "requires_external_tools": False,
        "broker_execution": False,
        "skill_pack_version": SKILL_PACK_VERSION,
    }
