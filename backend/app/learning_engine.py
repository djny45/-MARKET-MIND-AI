"""Evidence-based learning summaries for specialist research agents.

This module evaluates stored feedback and improvement proposals. It does not
modify model weights, agent prompts, strategy parameters, or execute trades.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
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
    feedback_times = [
        parsed for item in feedback
        if (parsed := _parse_time(item.get("created_at"))) is not None
    ]
    latest = max(feedback_times, default=None)

    # Compare older and newer scored feedback only when both windows have
    # enough observations. This is descriptive trend, not a causal claim.
    dated_scored = [
        (parsed, item) for item in scored
        if (parsed := _parse_time(item.get("created_at"))) is not None
    ]
    dated_scored.sort(key=lambda pair: pair[0])
    trend = {
        "status": "insufficient_feedback",
        "older_window_count": 0,
        "newer_window_count": 0,
        "older_window_score": None,
        "newer_window_score": None,
        "score_delta": None,
        "minimum_per_window": 3,
    }
    if len(dated_scored) >= 6:
        split = len(dated_scored) // 2
        older = [item for _, item in dated_scored[:split]]
        newer = [item for _, item in dated_scored[split:]]
        older_score = sum(_SCORE[item["content"]["outcome"]] for item in older) / len(older)
        newer_score = sum(_SCORE[item["content"]["outcome"]] for item in newer) / len(newer)
        trend = {
            "status": "descriptive_trend_available",
            "older_window_count": len(older),
            "newer_window_count": len(newer),
            "older_window_score": round(older_score, 4),
            "newer_window_score": round(newer_score, 4),
            "score_delta": round(newer_score - older_score, 4),
            "minimum_per_window": 3,
            "interpretation": "Reviewer-label trend only; not proof of research accuracy, causality, or trading performance.",
        }
    return {
        "worker_id": worker_id,
        "feedback_count": len(feedback),
        "scored_feedback_count": len(scored),
        "feedback_outcomes": outcomes,
        "observed_feedback_score": round(score, 4) if score is not None else None,
        "latest_feedback_at": latest.isoformat() if latest else None,
        "feedback_trend": trend,
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
    score_values = [
        (agent["observed_feedback_score"], agent["scored_feedback_count"])
        for agent in agents
        if agent["observed_feedback_score"] is not None and agent["scored_feedback_count"] > 0
    ]
    weighted_score = (
        sum(score * count for score, count in score_values)
        / sum(count for _, count in score_values)
        if score_values else None
    )
    return {
        "agent_count": len(agents),
        "agents_with_feedback": sum(agent["feedback_count"] > 0 for agent in agents),
        "total_feedback_records": total_feedback,
        "scored_feedback_records": scored,
        "unverified_feedback_records": total_feedback - scored,
        "improvement_proposals": proposals,
        "agents": agents,
        "system_feedback_score": round(weighted_score, 4) if weighted_score is not None else None,
        "score_note": "Descriptive reviewer feedback only; not a measured trading edge or financial performance metric.",
        "learning_mode": "feedback_evaluation_and_human_review",
        "autonomous_model_training": False,
        "automatic_agent_updates": False,
        "broker_execution": False,
    }

def run_feedback_improvement_cycle(worker_id: str, limit: int = 50, min_feedback: int = 5) -> dict[str, Any]:
    """Turn repeated reviewer feedback into a bounded, review-only improvement proposal.

    This is deterministic feedback summarization, not model training or automatic
    code/strategy modification. Feedback categories are caller-supplied labels;
    the cycle does not independently verify their correctness.
    """
    from .worker_memory import append_memory

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if isinstance(min_feedback, bool) or not isinstance(min_feedback, int) or not 5 <= min_feedback <= 50:
        raise ValueError("min_feedback must be between 5 and 50")

    summary = agent_learning_summary(worker_id, limit)
    records = read_memory(worker_id, "validation_result", limit)["memory"]
    scored = [
        item for item in records
        if isinstance(item.get("content"), dict)
        and item["content"].get("outcome") in _SCORE
    ]
    if len(scored) < min_feedback:
        return {
            "worker_id": worker_id, "cycle_status": "insufficient_feedback",
            "scored_feedback_count": len(scored), "minimum_required": min_feedback,
            "proposal_created": False, "model_training": False, "auto_apply": False,
        }

    weak = [
        item for item in scored
        if item["content"].get("outcome") in {"not_helpful", "partially_helpful"}
    ]
    if not weak:
        return {
            "worker_id": worker_id, "cycle_status": "no_negative_or_partial_feedback",
            "scored_feedback_count": len(scored),
            "feedback_score": summary["observed_feedback_score"],
            "proposal_created": False, "model_training": False, "auto_apply": False,
        }

    # Category tags are reviewer-provided evidence. Unknown/malformed tags are
    # conservatively grouped as "other"; no automatic semantic classification.
    categories = {
        "data_provenance": "Add source identity, retrieval timestamp, and provenance completeness checks.",
        "timestamp_leakage": "Add explicit timestamp alignment and future-information leakage tests.",
        "missing_data": "Add missingness, coverage, and incomplete-sample warnings to the research output.",
        "uncertainty": "Report sample size, uncertainty, and stability across chronological windows.",
        "reproducibility": "Record dataset/version/config fingerprints and a reproducible evaluation procedure.",
        "output_clarity": "Separate evidence, calculations, assumptions, and unknowns in the output schema.",
        "other": "Create a narrowly scoped quality-check candidate based on reviewer examples, then test it on held-out feedback.",
    }
    category_counts = {}
    examples = {}
    for item in weak:
        content = item["content"]
        raw_category = content.get("issue_category")
        category = raw_category if isinstance(raw_category, str) and raw_category in categories else "other"
        category_counts[category] = category_counts.get(category, 0) + 1
        issue_text = content.get("summary")
        if isinstance(issue_text, str) and issue_text.strip():
            examples.setdefault(category, [])
            clean_issue = issue_text.strip()[:300]
            if clean_issue not in examples[category] and len(examples[category]) < 3:
                examples[category].append(clean_issue)

    dominant_category = sorted(category_counts, key=lambda name: (-category_counts[name], name))[0]
    dominant_count = category_counts[dominant_category]
    example_notes = examples.get(dominant_category, [])
    evidence_refs = [
        "worker-memory:" + item["memory_id"]
        for item in weak[:30] if isinstance(item.get("memory_id"), str) and item["memory_id"]
    ]
    feedback_ids = sorted(
        item.get("memory_id", "") for item in scored
        if isinstance(item.get("memory_id"), str)
    )
    fingerprint_payload = {
        "worker_id": worker_id,
        "feedback_ids": feedback_ids,
        "dominant_issue_category": dominant_category,
        "category_counts": category_counts,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    existing = read_memory(worker_id, "method_note", 200)["memory"]
    for item in existing:
        saved = item.get("content", {}).get("update_proposal")
        if isinstance(saved, dict) and saved.get("cycle_fingerprint") == fingerprint:
            return {
                "worker_id": worker_id, "cycle_status": "proposal_already_exists",
                "proposal_memory_id": item["memory_id"], "proposal_created": False,
                "model_training": False, "auto_apply": False,
            }

    example_text = " | ".join(example_notes) if example_notes else "No reviewer summary was supplied."
    proposal = {
        "title": "Improve research quality: " + dominant_category.replace("_", " "),
        "rationale": (
            f"{dominant_category} was the most frequent tagged issue "
            f"({dominant_count} of {len(weak)} weak/partial feedback records). "
            f"Reviewer examples: {example_text}"
        )[:2000],
        "proposed_change": categories[dominant_category],
        "dominant_issue_category": dominant_category,
        "feedback_sample_count": len(scored),
        "weak_or_partial_feedback_count": len(weak),
        "issue_category_counts": dict(sorted(category_counts.items())),
        "evidence_refs": evidence_refs,
        "cycle_fingerprint": fingerprint,
        "status": "pending_review",
        "auto_apply": False,
        "requires_tests": True,
        "requires_rollback_plan": True,
        "training_scope": "research_quality_only_no_financial_strategy",
        "evaluation_plan": (
            "Compare candidate and baseline on a held-out feedback set; record "
            "sample counts, regressions, uncertainty, and reviewer decision."
        ),
    }
    record = append_memory(
        worker_id, "method_note", {"update_proposal": proposal},
        source_refs=evidence_refs, quality_status="unverified",
    )
    return {
        "worker_id": worker_id, "cycle_status": "proposal_created_pending_review",
        "proposal_memory_id": record["memory_id"], "proposal": proposal,
        "proposal_created": True, "model_training": False, "auto_apply": False,
        "note": (
            "Feedback-driven proposal generation is active; this aggregates reviewer labels "
            "and issue tags only. It does not train weights, alter strategy, or deploy changes."
        ),
    }
