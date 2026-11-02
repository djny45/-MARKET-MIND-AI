"""Allowlisted research playbook catalog; execution/broker skills are excluded."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "day-trader-skill"
REA_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "rea"
STAGESHOW_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "stageshow"
MARKET_DATA_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "market-data-yahoo"

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

REA_SKILL_DESCRIPTIONS = {
    "reverse-engineer-anything": "Evidence-led analysis of user-supplied applications, packages, and binaries.",
    "rea-analysis-optimization": "Optimize analysis workflows while preserving correctness and evidence.",
    "rea-ci-tests-audit": "Audit CI and tests for false passes, fixture drift, and missing regression coverage.",
    "rea-tool-design": "Design investigation tools, interfaces, provider contracts, and evidence semantics.",
}

MARKET_DATA_SKILL_DESCRIPTIONS = {
    "market-data-yahoo": "Yahoo Finance historical OHLCV retrieval and data-quality checks; research only.",
}

UI_SKILL_DESCRIPTIONS = {
    "stageshow": "Create polished React product UI mockups, dashboard stills, and cursor/motion demos; use only for frontend/design tasks.",
}


def list_skills():
    """Return only allowlisted research playbooks present in the repository."""
    trading = [
        {
            "id": slug,
            "description": description,
            "path": f".agents/skills/day-trader-skill/{slug}/SKILL.md",
            "available": (SKILL_ROOT / slug / "SKILL.md").is_file(),
            "mode": "research_and_paper_only",
            "requires_external_tools": False,
        }
        for slug, description in SKILL_DESCRIPTIONS.items()
    ]
    engineering = [
        {
            "id": slug,
            "description": description,
            "path": f".agents/skills/rea/{slug}/SKILL.md",
            "available": (REA_SKILL_ROOT / slug / "SKILL.md").is_file(),
            "mode": "engineering_research",
            "requires_external_tools": True,
        }
        for slug, description in REA_SKILL_DESCRIPTIONS.items()
    ]
    ui_design = [
        {
            "id": slug,
            "description": description,
            "path": ".agents/skills/stageshow/SKILL.md",
            "available": (STAGESHOW_SKILL_ROOT / "SKILL.md").is_file(),
            "mode": "ui_design_only",
            "requires_external_tools": True,
        }
        for slug, description in UI_SKILL_DESCRIPTIONS.items()
    ]
    market_data = [
        {
            "id": slug,
            "description": description,
            "path": ".agents/skills/market-data-yahoo/SKILL.md",
            "available": (MARKET_DATA_SKILL_ROOT / "SKILL.md").is_file(),
            "mode": "market_data_research_only",
            "requires_external_tools": True,
        }
        for slug, description in MARKET_DATA_SKILL_DESCRIPTIONS.items()
    ]
    return trading + engineering + ui_design + market_data


def load_skill(slug: str):
    """Load one allowlisted playbook; never resolve caller-supplied filesystem paths."""
    if slug in SKILL_DESCRIPTIONS:
        root = SKILL_ROOT
        description = SKILL_DESCRIPTIONS[slug]
        mode = "research_and_paper_only"
        requires_external_tools = False
    elif slug in REA_SKILL_DESCRIPTIONS:
        root = REA_SKILL_ROOT
        description = REA_SKILL_DESCRIPTIONS[slug]
        mode = "engineering_research"
        requires_external_tools = True
    elif slug in UI_SKILL_DESCRIPTIONS:
        root = STAGESHOW_SKILL_ROOT
        description = UI_SKILL_DESCRIPTIONS[slug]
        mode = "ui_design_only"
        requires_external_tools = True
    elif slug in MARKET_DATA_SKILL_DESCRIPTIONS:
        root = MARKET_DATA_SKILL_ROOT
        description = MARKET_DATA_SKILL_DESCRIPTIONS[slug]
        mode = "market_data_research_only"
        requires_external_tools = True
    else:
        raise KeyError(slug)

    path = root / "SKILL.md" if slug in UI_SKILL_DESCRIPTIONS or slug in MARKET_DATA_SKILL_DESCRIPTIONS else root / slug / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(slug)
    return {
        "id": slug,
        "description": description,
        "content": path.read_text(encoding="utf-8"),
        "mode": mode,
        "requires_external_tools": requires_external_tools,
        "broker_execution": False,
    }
