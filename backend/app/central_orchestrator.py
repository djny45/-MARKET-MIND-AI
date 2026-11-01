"""Central deterministic coordinator for bounded tasks and evidence synthesis."""
from .worker_coordinator import delegate_worker_tasks
from .cross_market_round import build_research_round


def coordinate_research(worker_tasks, values, messages, requested_markets=None,
                        min_sources_per_market=1):
    """Coordinate a caller-authored worker DAG and cross-market evidence gate."""
    delegation = delegate_worker_tasks(worker_tasks, values)
    evidence_round = build_research_round(
        messages, requested_markets=requested_markets,
        min_sources_per_market=min_sources_per_market,
    )
    ready = (
        delegation.get("status") == "completed"
        and evidence_round.get("status") == "ready_for_human_review"
    )
    return {
        "orchestrator_version": "2.0.0",
        "status": "ready_for_human_review" if ready else "incomplete_or_blocked",
        "worker_delegation": delegation,
        "cross_market_evidence": evidence_round,
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
