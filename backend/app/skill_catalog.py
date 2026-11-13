"""Allowlisted research playbook catalog; execution/broker skills are excluded."""
from pathlib import Path

from app.research_skill_pack import list_pack_skills, load_pack_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "day-trader-skill"
REA_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "rea"
STAGESHOW_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "stageshow"
MARKET_DATA_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "market-data-yahoo"
STOOQ_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "market-data-stooq"
QUANT_RESEARCH_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "quant-research-evaluation"
QLIB_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "qlib-research"
SOCIAL_RESEARCH_SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "social-research"

SKILL_DESCRIPTIONS = {
    "trader-alerts": "Historical data-quality and threshold-observation review.",
    "trader-analyst": "Source-cited issuer filings and public disclosure analysis.",
    "trader-budget": "Dataset, storage, and compute resource audit.",
    "trader-entry": "Retrospective pattern-label review.",
    "trader-exit": "Completed historical scenario review.",
    "trader-news": "Source-grounded news synthesis.",
    "trader-pelosi": "Public disclosure activity review.",
    "trader-risk": "Research methodology and bias audit.",
    "trader-scanner": "Historical instrument-universe coverage audit.",
    "trader-timemachine": "Empirical historical distribution analysis.",
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

STOOQ_SKILL_DESCRIPTIONS = {
    "market-data-stooq": "Stooq daily OHLCV retrieval and historical data-quality checks; research only.",
}

SOCIAL_RESEARCH_SKILL_DESCRIPTIONS = {
    "social-research": "Source-linked public social/community research via approved RSS feeds; coverage-limited and non-predictive.",
}

QUANT_RESEARCH_SKILL_DESCRIPTIONS = {
    "quant-research-evaluation": "Chronological evaluation, leakage checks, reproducibility and evidence-first research QA; informed by Qlib concepts.",
}

QLIB_SKILL_DESCRIPTIONS = {
    "qlib-research": "Qlib-inspired experiment design, chronological evaluation, and reproducible quantitative research; no copied Qlib implementation code.",
}

UI_SKILL_DESCRIPTIONS = {
    "stageshow": "Create polished React product UI mockups, dashboard stills, and cursor/motion demos; use only for frontend/design tasks.",
}


def list_skills():
    """Return only allowlisted research playbooks present in the repository."""
    historical_research = [
        {
            "id": slug,
            "description": description,
            "path": f".agents/skills/day-trader-skill/{slug}/SKILL.md",
            "available": (SKILL_ROOT / slug / "SKILL.md").is_file(),
            "mode": "historical_research_only",
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
    stooq_data = [
        {
            "id": slug,
            "description": description,
            "path": ".agents/skills/market-data-stooq/SKILL.md",
            "available": (STOOQ_SKILL_ROOT / "SKILL.md").is_file(),
            "mode": "market_data_research_only",
            "requires_external_tools": True,
        }
        for slug, description in STOOQ_SKILL_DESCRIPTIONS.items()
    ]
    quant_research = [
        {
            "id": slug,
            "description": description,
            "path": ".agents/skills/quant-research-evaluation/SKILL.md",
            "available": (QUANT_RESEARCH_SKILL_ROOT / "SKILL.md").is_file(),
            "mode": "research_evaluation_only",
            "requires_external_tools": False,
        }
        for slug, description in QUANT_RESEARCH_SKILL_DESCRIPTIONS.items()
    ]
    qlib_research = [
        {
            "id": slug,
            "description": description,
            "path": ".agents/skills/qlib-research/SKILL.md",
            "available": (QLIB_SKILL_ROOT / "SKILL.md").is_file(),
            "mode": "research_evaluation_only",
            "requires_external_tools": False,
            "upstream": "https://github.com/microsoft/qlib",
            "license_review_required_before_code_import": True,
        }
        for slug, description in QLIB_SKILL_DESCRIPTIONS.items()
    ]
    social_research = [
        {
            "id": slug,
            "description": description,
            "path": ".agents/skills/social-research/SKILL.md",
            "available": (SOCIAL_RESEARCH_SKILL_ROOT / "SKILL.md").is_file(),
            "mode": "social_research_only",
            "requires_external_tools": True,
        }
        for slug, description in SOCIAL_RESEARCH_SKILL_DESCRIPTIONS.items()
    ]
    return historical_research + engineering + ui_design + market_data + stooq_data + quant_research + qlib_research + social_research + list_pack_skills()


def load_skill(slug: str):
    """Load one allowlisted playbook; never resolve caller-supplied filesystem paths."""
    if slug.startswith("mm-skill-"):
        return load_pack_skill(slug)
    if slug in SKILL_DESCRIPTIONS:
        root = SKILL_ROOT
        description = SKILL_DESCRIPTIONS[slug]
        mode = "historical_research_only"
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
    elif slug in STOOQ_SKILL_DESCRIPTIONS:
        root = STOOQ_SKILL_ROOT
        description = STOOQ_SKILL_DESCRIPTIONS[slug]
        mode = "market_data_research_only"
        requires_external_tools = True
    elif slug in SOCIAL_RESEARCH_SKILL_DESCRIPTIONS:
        root = SOCIAL_RESEARCH_SKILL_ROOT
        description = SOCIAL_RESEARCH_SKILL_DESCRIPTIONS[slug]
        mode = "social_research_only"
        requires_external_tools = True
    elif slug in QUANT_RESEARCH_SKILL_DESCRIPTIONS:
        root = QUANT_RESEARCH_SKILL_ROOT
        description = QUANT_RESEARCH_SKILL_DESCRIPTIONS[slug]
        mode = "research_evaluation_only"
        requires_external_tools = False
    elif slug in QLIB_SKILL_DESCRIPTIONS:
        root = QLIB_SKILL_ROOT
        description = QLIB_SKILL_DESCRIPTIONS[slug]
        mode = "research_evaluation_only"
        requires_external_tools = False
    else:
        raise KeyError(slug)

    path = root / "SKILL.md" if slug in UI_SKILL_DESCRIPTIONS or slug in MARKET_DATA_SKILL_DESCRIPTIONS or slug in STOOQ_SKILL_DESCRIPTIONS or slug in QUANT_RESEARCH_SKILL_DESCRIPTIONS or slug in SOCIAL_RESEARCH_SKILL_DESCRIPTIONS or slug in QLIB_SKILL_DESCRIPTIONS else root / slug / "SKILL.md"
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


QLIB_RESEARCH_PROTOCOL = {
    "protocol_id": "qlib-historical-evaluation-v1",
    "skill_id": "qlib-research",
    "mode": "advisory_checklist",
    "steps": [
        "Define research question, target, horizon, dataset, and experiment version.",
        "Check data provenance, timestamps, missing values, duplicates, universe assumptions, and corporate actions.",
        "Use chronological train/validation/test splits; fit preprocessing on training data only.",
        "Check look-ahead leakage, publication delays, rolling-window overlap, and survivorship bias.",
        "Compare a simple baseline with the candidate; report sample counts, coverage, uncertainty, and time-window stability.",
        "Document any retrospective cost assumptions; never present historical estimates as current market outcomes.",
        "Record inputs, configuration, dataset identifiers, code revision, metrics, warnings, and random seeds.",
        "Require tests, independent review, and rollback planning before adopting changes.",
    ],
    "required_outputs": [
        "Experiment ID and version",
        "Dataset source, retrieval time, status, and date range",
        "Split boundaries and leakage checks",
        "Baseline and candidate metrics with sample counts",
        "Robustness checks and uncertainty",
        "Limitations and reviewer decision",
        "Reproduction command or procedure",
    ],
    "research_only": True,
    "broker_execution": False,
    "autonomous_model_update": False,
    "enforcement": "advisory_only_not_automatically_applied_to_node_execution",
}


def build_skill_protocol(slug: str) -> dict | None:
    """Return a fixed, allowlisted advisory protocol for supported research skills."""
    if slug == "qlib-research":
        # Return a fresh object so callers cannot mutate the module-level template.
        return {
            **QLIB_RESEARCH_PROTOCOL,
            "steps": list(QLIB_RESEARCH_PROTOCOL["steps"]),
            "required_outputs": list(QLIB_RESEARCH_PROTOCOL["required_outputs"]),
        }
    return None
