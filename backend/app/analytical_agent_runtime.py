"""Per-agent analytical brain configuration and governed learning lifecycle.

Each specialist AI agent has a distinct specialization/context and memory namespace while
sharing the configured intelligence provider. Learning records are evaluated
feedback and proposed configuration changes, not autonomous model-weight
training. Proposed updates require explicit review before application.
"""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar, Token
from .workers import list_workers

CORE_ID = "shared_central_intelligence"
WORKERS = {item["id"]: item for item in list_workers()}
MAX_CONTEXT_CHARS = 6000
MAX_FEEDBACK_CHARS = 4000
MAX_PROPOSAL_CHARS = 4000

# A task-local scope prevents concurrent specialist agents from observing one
# another's identity or task metadata. ContextVar follows asyncio task context;
# callers crossing raw thread/process boundaries must propagate context explicitly.
_AGENT_SCOPE: ContextVar[dict | None] = ContextVar("market_mind_agent_scope", default=None)


def set_agent_scope(worker_id: str, task_id: str) -> Token:
    """Bind an immutable-by-convention identity envelope for one task execution."""
    brain = brain_config(worker_id)
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 128:
        raise ValueError("task_id must be a non-empty string of at most 128 characters")
    scope = {
        "worker_id": worker_id,
        "task_id": task_id,
        "memory_namespace": brain["memory_namespace"],
        "intelligence_core": CORE_ID,
    }
    return _AGENT_SCOPE.set(scope)


@__import__("contextlib").contextmanager
def agent_scope(worker_id: str, task_id: str):
    """Context manager for isolated per-agent execution scopes."""
    token = set_agent_scope(worker_id, task_id)
    try:
        yield current_agent_scope()
    finally:
        reset_agent_scope(token)


def current_agent_scope() -> dict | None:
    """Return a defensive copy of the active task-local agent scope."""
    scope = _AGENT_SCOPE.get()
    return dict(scope) if scope is not None else None


def reset_agent_scope(token: Token) -> None:
    """Restore the caller's prior scope, including correctly nested executions."""
    _AGENT_SCOPE.reset(token)

def _bounded_text(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()

def brain_config(worker_id: str) -> dict:
    """Return a unique, deterministic brain/context specification for a worker."""
    worker = WORKERS.get(worker_id)
    if worker is None:
        raise ValueError("worker_id must identify a registered analytical agent")
    role = (
        f"You are {worker['name']}, a specialist analytical research agent in "
        f"{worker['department']}. Your specialty is {worker['specialty']}. "
        "Analyze only supplied data and research materials. Separate observations, "
        "calculations, assumptions, and unknowns. Cite supplied source references. "
        "Never invent data, claim certainty without evidence, or execute trades."
    )
    digest = hashlib.sha256(role.encode("utf-8")).hexdigest()
    return {
        "agent_id": worker_id,
        "agent_name": worker["name"],
        "department": worker["department"],
        "specialty": worker["specialty"],
        "brain_context": role,
        "brain_context_sha256": digest,
        "memory_namespace": worker["memory_namespace"],
        "intelligence_core": CORE_ID,
        "model_topology": "individual_agent_context_shared_inference_provider",
        "independent_model": False,
        "research_scope": "supplied_and_configured_research_data_only",
        "learning_mode": "evaluated_feedback_and_reviewed_proposals",
        "self_update_mode": "proposal_only_review_required",
        "broker_execution": False,
    }

def runtime_manifest() -> dict:
    departments = sorted({worker["department"] for worker in WORKERS.values()})
    return {
        "agent_count": len(WORKERS),
        "departments": departments,
        "agent_brains": "distinct_role_context_and_namespace",
        "inference": "shared_core_provider",
        "persistent_memory": "worker_scoped_sqlite_evidence_notes",
        "research": "assigned_tasks_over_supplied_or_configured_data",
        "learning": "feedback_records_and_reviewable_improvement_proposals",
        "self_update": "proposals_only; approval and rollback required",
        "autonomous_weight_training": False,
        "paper_trading": False,
        "broker_execution": False,
        "cloud_workspace": "not_yet_implemented",
        "note": "This manifest describes implemented agent context and governance scaffolding; it does not claim 550 independent model instances or autonomous cloud agents.",
    }

def validate_learning_feedback(worker_id: str, feedback: dict) -> dict:
    if worker_id not in WORKERS:
        raise ValueError("worker_id must identify a registered analytical agent")
    if not isinstance(feedback, dict):
        raise ValueError("feedback must be an object")
    summary = _bounded_text(feedback.get("summary"), "summary", MAX_FEEDBACK_CHARS)
    outcome = feedback.get("outcome")
    if outcome not in {"helpful", "partially_helpful", "not_helpful", "unverified"}:
        raise ValueError("outcome must be helpful, partially_helpful, not_helpful, or unverified")
    metrics = feedback.get("metrics", {})
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    try:
        encoded = json.dumps(metrics, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("metrics must be finite JSON data") from exc
    if len(encoded) > 2000:
        raise ValueError("metrics must not exceed 2000 characters")
    return {"worker_id": worker_id, "summary": summary, "outcome": outcome,
            "metrics": metrics, "learning_effect": "record_only_no_model_training"}

def validate_update_proposal(worker_id: str, proposal: dict) -> dict:
    if worker_id not in WORKERS:
        raise ValueError("worker_id must identify a registered analytical agent")
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object")
    title = _bounded_text(proposal.get("title"), "title", 160)
    rationale = _bounded_text(proposal.get("rationale"), "rationale", MAX_PROPOSAL_CHARS)
    proposed_change = _bounded_text(proposal.get("proposed_change"), "proposed_change", MAX_PROPOSAL_CHARS)
    evidence_refs = proposal.get("evidence_refs", [])
    if (not isinstance(evidence_refs, list) or len(evidence_refs) > 30
            or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 300 for ref in evidence_refs)):
        raise ValueError("evidence_refs must contain at most 30 non-empty strings of at most 300 characters")
    return {
        "worker_id": worker_id, "title": title, "rationale": rationale,
        "proposed_change": proposed_change, "evidence_refs": evidence_refs,
        "status": "pending_review",
        "auto_apply": False,
        "requires_tests": True,
        "requires_rollback_plan": True,
    }
