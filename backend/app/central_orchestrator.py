"""Central deterministic coordinator for bounded worker tasks and evidence synthesis."""
from .worker_coordinator import delegate_worker_tasks
from .research_orchestrator import build_research_brief


def coordinate_research(worker_tasks, values, findings, requested_markets=None):
    if not isinstance(findings, list) or len(findings) > 1000:
        raise ValueError("findings must be a list of at most 1000 records")
    requested = ["india", "us", "crypto", "forex"] if requested_markets is None else requested_markets
    delegation = delegate_worker_tasks(worker_tasks, values)
    brief = build_research_brief(findings, requested)
    source_coverage = {}
    for market in requested:
        refs = {
            ref for item in findings if item.get("market_group") == market
            and item.get("quality_status", "unverified") != "synthetic"
            for ref in item.get("source_refs", [])
        }
        source_coverage[market] = {"distinct_source_refs": len(refs), "status": "covered" if refs else "missing"}
    missing_sources = [market for market, item in source_coverage.items() if item["status"] != "covered"]
    ready = (
        delegation.get("status") == "completed"
        and not brief.get("missing_market_groups")
        and not missing_sources
    )
    return {
        "orchestrator_version": "2.1.0",
        "status": "ready_for_human_review" if ready else "incomplete_or_blocked",
        "worker_delegation": delegation,
        "research_brief": brief,
        "source_coverage_gate": {
            "requested_markets": requested,
            "per_market": source_coverage,
            "missing_source_markets": missing_sources,
            "gate": "passed" if not missing_sources else "blocked",
        },
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
