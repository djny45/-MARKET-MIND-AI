"""Deterministic routing from workflow node types to shared-core worker profiles.

Worker profiles are metadata templates. This router binds supported workflow
nodes to existing deterministic Python handlers; it does not perform LLM
inference or activate 550 independent model processes.
"""
from .workers import list_workers

CORE_ID = "shared_central_intelligence"

NODE_DEPARTMENTS = {
    "market_input": "data_quality",
    "data_quality": "data_quality",
    "sma": "technical_analysis",
    "ema": "technical_analysis",
    "rsi": "technical_analysis",
    "macd": "technical_analysis",
    "bollinger": "technical_analysis",
    "returns": "quantitative_research",
    "volatility": "quantitative_research",
    "research_summary": "research_validation",
}

_WORKERS = list_workers()
_BY_ID = {worker["id"]: worker for worker in _WORKERS}
_BY_DEPARTMENT = {}
for _worker in _WORKERS:
    _BY_DEPARTMENT.setdefault(_worker["department"], []).append(_worker)


def assign_worker(node_type: str, requested_worker_id: str | None = None) -> dict:
    """Return a validated worker profile and explicit execution boundary."""
    if node_type not in NODE_DEPARTMENTS:
        raise ValueError(f"No worker routing is defined for node type: {node_type}")
    if requested_worker_id is not None:
        if not isinstance(requested_worker_id, str) or requested_worker_id not in _BY_ID:
            raise ValueError("worker_id must identify a registered worker template")
        profile = _BY_ID[requested_worker_id]
        expected_department = NODE_DEPARTMENTS[node_type]
        if profile["department"] != expected_department:
            raise ValueError(
                f"worker_id department must be {expected_department} for {node_type}"
            )
    else:
        profile = _BY_DEPARTMENT[NODE_DEPARTMENTS[node_type]][0]
    return {
        "worker_id": profile["id"],
        "worker_name": profile["name"],
        "department": profile["department"],
        "specialty": profile["specialty"],
        "intelligence_core": CORE_ID,
        "execution_mode": "deterministic_analytical_handler",
        "profile_status": profile["status"],
    }


def worker_runtime_status() -> dict:
    """Describe implemented handler coverage without overstating AI capability."""
    return {
        "intelligence_core": CORE_ID,
        "worker_profile_count": len(_WORKERS),
        "routable_node_types": sorted(NODE_DEPARTMENTS),
        "routed_departments": sorted(set(NODE_DEPARTMENTS.values())),
        "execution_mode": "deterministic_analytical_handlers",
        "llm_inference_enabled": False,
        "broker_execution": False,
        "note": (
            "Workflow nodes are routed to specialist worker profiles and existing "
            "deterministic handlers. Profiles are not independent models; LLM "
            "inference and autonomous learning are not enabled."
        ),
    }
