"""Central deterministic coordinator for bounded worker tasks and evidence synthesis."""
from .worker_coordinator import delegate_worker_tasks
from .research_orchestrator import build_research_brief


def coordinate_research(worker_tasks, values, findings, requested_markets=None):
    if not isinstance(findings, list) or len(findings) > 1000:
        raise ValueError("findings must be a list of at most 1000 records")
    delegation = delegate_worker_tasks(worker_tasks, values)
    brief = build_research_brief(findings, requested_markets)
    ready = delegation.get("status") == "completed" and not brief.get("missing_market_groups")
    return {
        "orchestrator_version": "2.0.0",
        "status": "ready_for_human_review" if ready else "incomplete_or_blocked",
        "worker_delegation": delegation,
        "research_brief": brief,
        "coordination_policy": {
            "worker_tasks_are_bounded": True,
            "evidence_is_caller_supplied": True,
            "human_review_required": True,
            "autonomous_inference": False,
            "external_data_retrieval": False,
            "order_execution": False,
        },
        "research_only": True,
    }
