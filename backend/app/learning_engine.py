"""Evidence-based learning summaries for specialist research agents.

This module evaluates stored feedback and improvement proposals. It does not
modify model weights, agent prompts, strategy parameters, or execute trades.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .worker_memory import read_memory
from .workers import list_workers

_SCORE = {"helpful": 1.0, "partially_helpful": 0.5, "not_helpful": 0.0}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def agent_learning_summary(worker_id: str, limit: int = 200) -> dict[str, Any]:
    """Summarize feedback and proposed improvements for one registered worker."""
    feedback_result = read_memory(worker_id, "validation_result", limit)
    proposal_result = read_memory(worker_id, "method_note", limit)
    feedback = [
        item for item in feedback_result["memory"]
        if isinstance(item.get("content"), dict)
        and item["content"].get("outcome") in {*_SCORE, "unverified"}
    ]
    scored = [item for item in feedback if item["content"].get("outcome") in _SCORE]
    outcomes = {name: sum(item["content"].get("outcome") == name for item in feedback)
                for name in (*_SCORE, "unverified")}
    score = sum(_SCORE[item["content"]["outcome"]] for item in scored) / len(scored) if scored else None
    proposals = [
        item for item in proposal_result["memory"]
        if isinstance(item.get("content"), dict) and "update_proposal" in item["content"]
    ]
    latest = max((_parse_time(item.get("created_at")) for item in feedback), default=None)
    return {
        "worker_id": worker_id,
        "feedback_count": len(feedback),
        "scored_feedback_count": len(scored),
        "feedback_outcomes": outcomes,
        "observed_feedback_score": round(score, 4) if score is not None else None,
        "latest_feedback_at": latest.isoformat() if latest else None,
        "improvement_proposals": len(proposals),
        "evaluation_status": "insufficient_feedback" if len(scored) < 5 else "review_required",
        "minimum_feedback_for_trend": 5,
        "score_definition": "mean of reviewer labels: helpful=1, partially_helpful=0.5, not_helpful=0; unverified excluded",
        "model_training": False,
        "auto_apply": False,
    }


def learning_overview(limit_per_agent: int = 200) -> dict[str, Any]:
    """Return a bounded system-wide learning-feedback and proposal overview."""
    if isinstance(limit_per_agent, bool) or not isinstance(limit_per_agent, int) or not 1 <= limit_per_agent <= 200:
        raise ValueError("limit_per_agent must be between 1 and 200")
    agents = [agent_learning_summary(agent["id"], limit_per_agent) for agent in list_workers()]
    total_feedback = sum(agent["feedback_count"] for agent in agents)
    scored = sum(agent["scored_feedback_count"] for agent in agents)
    proposals = sum(agent["improvement_proposals"] for agent in agents)
    score_values = [agent["observed_feedback_score"] for agent in agents
                    if agent["observed_feedback_score"] is not None]
    return {
        "agent_count": len(agents),
        "agents_with_feedback": sum(agent["feedback_count"] > 0 for agent in agents),
        "total_feedback_records": total_feedback,
        "scored_feedback_records": scored,
        "unverified_feedback_records": total_feedback - scored,
        "improvement_proposals": proposals,
        "agents": agents,
        "system_feedback_score": round(sum(score_values) / len(score_values), 4) if score_values else None,
        "score_note": "Descriptive reviewer feedback only; not a measured trading edge or financial performance metric.",
        "learning_mode": "feedback_evaluation_and_human_review",
        "autonomous_model_training": False,
        "automatic_agent_updates": False,
        "broker_execution": False,
    }
