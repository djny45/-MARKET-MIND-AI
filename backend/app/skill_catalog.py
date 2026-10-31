"""Allowlisted research playbook catalog; execution/broker skills are excluded."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "day-trader-skill"

SKILL_DESCRIPTIONS = {
    "trader-alerts": "Alert interpretation and notification research.",
    "trader-analyst": "Company and market fundamental research.",
    "trader-budget": "Research budget and resource planning.",
    "trader-entry": "Paper-only scenario entry criteria.",
    "trader-exit": "Paper-only scenario exit criteria.",
    "trader-news": "News and event context analysis.",
    "trader-pelosi": "Public-disclosure tracking and source verification.",
    "trader-risk": "Risk measurement and scenario controls.",
    "trader-scanner": "Market and instrument screening.",
    "trader-timemachine": "Historical and time-series research.",
}


def list_skills():
    """Return only allowlisted research playbooks present in the repository."""
    return [
        {
            "id": slug,
            "description": description,
            "path": f".agents/skills/day-trader-skill/{slug}/SKILL.md",
            "available": (SKILL_ROOT / slug / "SKILL.md").is_file(),
            "mode": "research_and_paper_only",
        }
        for slug, description in SKILL_DESCRIPTIONS.items()
    ]


def load_skill(slug: str):
    """Load one allowlisted playbook; never resolve caller-supplied filesystem paths."""
    if slug not in SKILL_DESCRIPTIONS:
        raise KeyError(slug)
    path = SKILL_ROOT / slug / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(slug)
    return {
        "id": slug,
        "description": SKILL_DESCRIPTIONS[slug],
        "content": path.read_text(encoding="utf-8"),
        "mode": "research_and_paper_only",
        "broker_execution": False,
    }
