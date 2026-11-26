"""Research routing for the integrated exchange-intelligence capabilities.

EXTENDS the existing 550-agent registry, 300-skill catalog and worker-memory
architecture. It does NOT create new agents, new skills or a second memory
system:

* Skills are selected from the existing ``skill_catalog`` allowlist (verified
  by name against ``list_skills``). The new topics map to skills that already
  exist in the 300-skill pack (funding, open interest, liquidations,
  commodity volatility, sentiment, correlation).
* Findings are stored with the existing ``worker_memory`` contract, which
  already carries source refs, quality status and content JSON.
* Every finding separates OBSERVED FACTS from CALCULATED INDICATORS and
  AI INTERPRETATIONS, and carries source, retrieval and event timestamps,
  confidence and limitations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Existing skill ids from the 300-skill catalog — verified at runtime.
TOPIC_SKILLS: dict[str, tuple[str, str]] = {
    "crypto_order_flow": (
        "mm-skill-168", "Funding Rate Interpretation",
    ),
    "liquidations": (
        "mm-skill-170", "Liquidation Data Caveats",
    ),
    "open_interest": (
        "mm-skill-169", "Open Interest Analysis",
    ),
    "gold_activity": (
        "mm-skill-199", "Commodity Volatility Research",
    ),
    "options_volatility": (
        "mm-skill-081", "Historical Volatility Analysis",
    ),
    "indian_derivatives": (
        "mm-skill-081", "Historical Volatility Analysis",
    ),
    "fear_greed": (
        "mm-skill-220", "Sentiment Research Summary",
    ),
    "cross_market": (
        "mm-skill-096", "Volatility Regime Comparison",
    ),
}


def supported_topics() -> list[str]:
    return sorted(TOPIC_SKILLS)


def resolve_skill(topic: str) -> dict[str, Any]:
    """Return the existing skill id for a research topic; never invent one."""
    normalized = topic.strip().lower()
    entry = TOPIC_SKILLS.get(normalized)
    if entry is None:
        raise ValueError(
            "unsupported topic; choose one of " + ", ".join(supported_topics())
        )
    from .skill_catalog import list_skills

    available = {item["id"] for item in list_skills()}
    skill_id, title = entry
    if skill_id not in available:
        # Withhold a claim we cannot verify; do not fall back to a new skill.
        return {
            "topic": normalized, "skill_id": None, "skill_title": title,
            "available": False,
            "note": "Mapped skill is not currently allowlisted; no skill was substituted.",
        }
    return {
        "topic": normalized, "skill_id": skill_id, "skill_title": title,
        "available": True, "agent_pool": "existing_550_worker_registry",
        "new_agents_created": False, "new_skills_created": False,
    }


def build_research_finding(
    *,
    topic: str,
    instrument: str,
    market: str,
    source: str,
    event_timestamp: str | None,
    retrieval_timestamp: str | None,
    observed_facts: list[str],
    calculated_indicators: dict[str, Any] | None = None,
    interpretation: str | None = None,
    evidence: list[str] | None = None,
    confidence: str = "low",
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    """Build a finding compatible with the existing worker_memory schema.

    ``interpretation`` is explicitly labelled as an AI-generated hypothesis,
    never an observed fact. No field is optional when the value is unknown:
    ``None`` is used so missing provenance stays visible.
    """
    if confidence not in {"low", "medium", "high"}:
        raise ValueError("confidence must be low, medium or high")
    if not instrument.strip() or not source.strip():
        raise ValueError("instrument and source are required")
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "memory_type": "observation",
        "created_at": timestamp,
        "content_json": {
            "topic": topic,
            "instrument": instrument,
            "market": market,
            "provenance": {
                "source": source,
                "event_timestamp": event_timestamp,
                "retrieval_timestamp": retrieval_timestamp,
            },
            "observed_facts": list(observed_facts),
            "calculated_indicators": calculated_indicators or {},
            "ai_interpretation": interpretation,
            "interpretation_label": (
                "AI-generated hypothesis; not an observed fact" if interpretation else None
            ),
            "evidence": list(evidence or []),
            "confidence": confidence,
            "limitations": list(limitations or []),
            "data_boundary": {
                "broker_execution": False,
                "real_money": False,
                "broker_credentials_seen": False,
            },
        },
        "quality_status": "pending_review",
        "source_refs_json": [source],
        "note": (
            "Store through the existing worker_memory API. This function only "
            "builds the payload; it does not create a new memory subsystem."
        ),
    }


def manifest() -> dict[str, Any]:
    return {
        "mode": "existing_agent_ecosystem_extension",
        "agent_registry": "existing_550_workers",
        "skill_catalog": "existing_300_pack_plus_allowlisted_skills",
        "topics": supported_topics(),
        "new_agents_created": False,
        "new_skills_created": False,
        "new_memory_system_created": False,
        "credential_isolation": {
            "broker_credentials_sent_to_agents": False,
            "broker_credentials_logged": False,
            "broker_credentials_in_shared_memory": False,
        },
    }
