"""Evidence-based learning summaries for specialist research agents.

This module evaluates stored feedback and improvement proposals. It does not
modify model weights, agent prompts, strategy parameters, or execute trades.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
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

def run_feedback_improvement_cycle(worker_id: str, limit: int = 50, min_feedback: int = 5) -> dict[str, Any]:
    """Create a review-only research-quality proposal from sufficient feedback."""
    from .worker_memory import append_memory

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if isinstance(min_feedback, bool) or not isinstance(min_feedback, int) or not 5 <= min_feedback <= 50:
        raise ValueError("min_feedback must be between 5 and 50")

    summary = agent_learning_summary(worker_id, limit)
    records = read_memory(worker_id, "validation_result", limit)["memory"]
    scored = [item for item in records if isinstance(item.get("content"), dict)
              and item["content"].get("outcome") in _SCORE]
    if len(scored) < min_feedback:
        return {"worker_id": worker_id, "cycle_status": "insufficient_feedback",
                "scored_feedback_count": len(scored), "minimum_required": min_feedback,
                "proposal_created": False, "model_training": False, "auto_apply": False}

    weak = [item for item in scored if item["content"].get("outcome") in {"not_helpful", "partially_helpful"}]
    if not weak:
        return {"worker_id": worker_id, "cycle_status": "no_negative_or_partial_feedback",
                "scored_feedback_count": len(scored), "feedback_score": summary["observed_feedback_score"],
                "proposal_created": False, "model_training": False, "auto_apply": False}

    sample = weak[0]
    issue = str(sample["content"].get("summary", "Reviewer feedback indicates output-quality gap"))[:800]
    evidence_id = sample.get("memory_id", "")
    fingerprint_payload = {"worker_id": worker_id,
        "feedback_ids": sorted(item.get("memory_id", "") for item in scored), "issue": issue}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    existing = read_memory(worker_id, "method_note", 200)["memory"]
    for item in existing:
        saved = item.get("content", {}).get("update_proposal")
        if isinstance(saved, dict) and saved.get("cycle_fingerprint") == fingerprint:
            return {"worker_id": worker_id, "cycle_status": "proposal_already_exists",
                    "proposal_memory_id": item["memory_id"], "proposal_created": False,
                    "model_training": False, "auto_apply": False}

    proposal = {"title": "Improve research output quality from reviewer feedback",
        "rationale": "Feedback cycle found a quality gap. Example reviewer note: " + issue,
        "proposed_change": "In a staging-only candidate, add explicit checks for provenance, timestamps, uncertainty, and missing-data disclosure. Evaluate on held-out feedback before any human-approved rollout.",
        "evidence_refs": ["worker-memory:" + evidence_id] if evidence_id else [],
        "cycle_fingerprint": fingerprint, "status": "pending_review", "auto_apply": False,
        "requires_tests": True, "requires_rollback_plan": True,
        "training_scope": "research_quality_only_no_financial_strategy"}
    record = append_memory(worker_id, "method_note", {"update_proposal": proposal},
        source_refs=proposal["evidence_refs"], quality_status="unverified")
    return {"worker_id": worker_id, "cycle_status": "proposal_created_pending_review",
        "proposal_memory_id": record["memory_id"], "proposal": proposal,
        "proposal_created": True, "model_training": False, "auto_apply": False,
        "note": "Feedback-driven proposal generation is active; model-weight training and automatic deployment remain disabled."}
