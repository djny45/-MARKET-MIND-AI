"""Bounded synchronous dispatch for implemented analytical worker capabilities.

Worker profiles remain templates. A profile can execute only an explicitly
mapped deterministic workflow operation; this module does not invoke an LLM,
fetch market data, or place orders.
"""
from .workers import list_workers
from .workflow import NODE_TYPES, execute_workflow

# Explicit opt-in mappings. Unmapped specialties remain descriptive templates.
SPECIALTY_OPERATIONS = {
    "trend": {"sma", "ema"},
    "momentum": {"rsi", "macd"},
    "mean_reversion": {"bollinger"},
    "statistical_validation": {"data_quality"},
    "research_synthesis": {"research_summary"},
    "volatility": {"volatility"},
    "relative_strength": {"returns"},
}

def worker_capabilities():
    workers = list_workers()
    executable = []
    for worker in workers:
        operations = sorted(SPECIALTY_OPERATIONS.get(worker["specialty"], set()))
        executable.append({
            "worker_id": worker["id"],
            "department": worker["department"],
            "specialty": worker["specialty"],
            "status": "executable" if operations else "template",
            "supported_operations": operations,
            "model": "deterministic_workflow_engine" if operations else None,
        })
    executable_count = sum(item["status"] == "executable" for item in executable)
    return {
        "worker_profiles": len(workers),
        "executable_profiles": executable_count,
        "template_only_profiles": len(workers) - executable_count,
        "execution_mode": "synchronous_deterministic",
        "capabilities": executable,
        "limitations": [
            "Executable means only the listed deterministic workflow operation is wired.",
            "No profile performs independent LLM inference or autonomous market research.",
            "No live market-data access, forecasts, investment advice or order execution.",
        ],
    }

def dispatch_worker_task(worker_id, operation, values, params=None):
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("worker_id is required")
    if operation not in NODE_TYPES or operation == "market_input":
        raise ValueError("operation is not an executable analytical operation")
    worker = next((item for item in list_workers() if item["id"] == worker_id), None)
    if worker is None:
        raise KeyError("worker_id was not found")
    allowed = SPECIALTY_OPERATIONS.get(worker["specialty"], set())
    if operation not in allowed:
        raise PermissionError("worker profile is not authorized for this operation")
    if not isinstance(values, list) or not 2 <= len(values) <= 10000:
        raise ValueError("values must contain between 2 and 10000 observations")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    node = {"id": "worker-task", "type": operation, "data": params}
    result = execute_workflow([node], [], {"worker-task": values}, max_workers=1)
    task = result["tasks"][0]
    return {
        "worker_id": worker_id,
        "worker_name": worker["name"],
        "department": worker["department"],
        "specialty": worker["specialty"],
        "operation": operation,
        "status": task["status"],
        "execution_mode": "synchronous_deterministic",
        "result": result["results"].get("worker-task"),
        "task": task,
        "research_only": True,
    }
