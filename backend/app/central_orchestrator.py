"""Central deterministic coordinator for bounded research tasks and evidence synthesis."""
from .worker_delegation import delegate_worker_tasks
from .research_orchestrator import build_research_brief

def coordinate_research(worker_tasks, findings, requested_markets=None):
    if not isinstance(findings, list) or len(findings) > 1000:
        raise ValueError("findings must be a list of at most 1000 records")
    delegation = delegate_worker_tasks(worker_tasks)
    brief = build_research_brief(findings, requested_markets)
    return {
        "orchestrator_version": "1.0.0",
        "status": "ready_for_human_review" if brief.get("missing_market_groups") == [] else "incomplete_market_coverage",
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
