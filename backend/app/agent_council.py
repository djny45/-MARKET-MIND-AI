"""Bounded multi-agent analytical council using specialist AI agent contexts.

Each council member is a registered specialist agent with a distinct role/context.
Members share the same configured inference provider; this is collaboration across
agent identities, not separate foundation models. Outputs are evidence-limited.
"""
from __future__ import annotations

import json
from .analytical_agent_runtime import brain_config
from .intelligence_core import synthesize_research

MAX_COUNCIL_SIZE = 8
MAX_BRIEF_CHARS = 4000
MAX_DATA_CHARS = 10000


def run_agent_council(agent_ids: list[str], brief: str, data: dict | list | None = None) -> dict:
    if not isinstance(agent_ids, list) or not 1 <= len(agent_ids) <= MAX_COUNCIL_SIZE:
        raise ValueError(f"agent_ids must contain between 1 and {MAX_COUNCIL_SIZE} registered agents")
    if len(set(agent_ids)) != len(agent_ids):
        raise ValueError("agent_ids must be unique")
    if not isinstance(brief, str) or not brief.strip() or len(brief) > MAX_BRIEF_CHARS:
        raise ValueError("brief must be a non-empty string of at most 4000 characters")
    if data is not None and not isinstance(data, (dict, list)):
        raise ValueError("data must be a JSON object or array")
    try:
        encoded_data = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("data must contain finite JSON-compatible values") from exc
    if len(encoded_data) > MAX_DATA_CHARS:
        raise ValueError(f"data must not exceed {MAX_DATA_CHARS} characters")

    members = []
    for agent_id in agent_ids:
        brain = brain_config(agent_id)
        member_input = {
            "agent_identity": {
                "id": brain["agent_id"],
                "name": brain["agent_name"],
                "department": brain["department"],
                "specialty": brain["specialty"],
                "brain_context": brain["brain_context"],
                "brain_context_sha256": brain["brain_context_sha256"],
                "memory_namespace": brain["memory_namespace"],
            },
            "brief": brief.strip(),
            "supplied_data": data,
            "instructions": [
                "Respond only from the supplied data and task brief.",
                "Clearly separate observations, assumptions, and unknowns.",
                "Identify evidence gaps and avoid unsupported conclusions.",
                "Do not provide trade execution instructions or claim investment certainty.",
            ],
        }
        synthesis = synthesize_research(member_input)
        members.append({
            "agent_id": agent_id,
            "agent_name": brain["agent_name"],
            "department": brain["department"],
            "specialty": brain["specialty"],
            "brain_context_sha256": brain["brain_context_sha256"],
            "memory_namespace": brain["memory_namespace"],
            "status": synthesis.get("status", "unknown"),
            "analysis": synthesis.get("summary"),
            "provider_reason": synthesis.get("reason"),
        })

    available = [member for member in members if member["status"] == "completed" and member["analysis"]]
    # No fabricated voting/consensus: report provider outputs and availability honestly.
    return {
        "brief": brief.strip(),
        "agent_count_requested": len(agent_ids),
        "agent_count_with_analysis": len(available),
        "shared_core": "shared_central_intelligence",
        "inference_topology": "specialist_agent_contexts_shared_provider",
        "members": members,
        "synthesis_status": "completed" if available else "provider_unavailable_or_not_configured",
        "consensus": None,
        "consensus_note": "No consensus is asserted; cross-agent synthesis and disagreement scoring are future work.",
        "research_boundary": "supplied_data_only_no_live_market_fetch",
        "paper_trading": False,
        "broker_execution": False,
    }
