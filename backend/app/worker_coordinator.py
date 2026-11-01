"""Bounded worker-to-worker delegation over an explicit caller-authored DAG.

This coordinator routes deterministic analytical operations only. It does not
invent tasks, invoke LLMs, fetch data, or perform trading actions.
"""
from .worker_runtime import worker_capabilities, dispatch_worker_task

ALLOWED_OPERATIONS = {"sma", "ema", "rsi", "macd", "bollinger", "returns", "volatility", "data_quality", "research_summary"}


def _numeric_series(result):
    if isinstance(result, list):
        candidate = result
    elif isinstance(result, dict):
        candidate = next((result[key] for key in ("series", "macd", "histogram", "middle", "upper", "lower")
                          if isinstance(result.get(key), list)), None)
    else:
        candidate = None
    if not isinstance(candidate, list) or len(candidate) < 2:
        raise ValueError("dependency output does not expose a numeric series")
    try:
        values = [float(value) for value in candidate]
    except (TypeError, ValueError) as exc:
        raise ValueError("dependency output series is not numeric") from exc
    return values


def delegate_worker_tasks(tasks, values):
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 25:
        raise ValueError("tasks must contain between 1 and 25 task definitions")
    if not isinstance(values, list) or not 2 <= len(values) <= 10000:
        raise ValueError("values must contain between 2 and 10000 observations")
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("each task must be an object")
        task_id = task.get("task_id")
        operation = task.get("operation")
        dependencies = task.get("depends_on", [])
        if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 64 or task_id in by_id:
            raise ValueError("task_id must be unique, non-empty, and at most 64 characters")
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError("unsupported delegated operation")
        if not isinstance(dependencies, list) or len(dependencies) > 1 or any(not isinstance(x, str) for x in dependencies):
            raise ValueError("each task may depend on at most one prior task")
        by_id[task_id] = task

    for task in tasks:
        if any(dep not in by_id for dep in task.get("depends_on", [])):
            raise ValueError("task dependency does not exist")
    indegree = {task_id: len(task.get("depends_on", [])) for task_id, task in by_id.items()}
    ordered, ready = [], [task_id for task_id, degree in indegree.items() if degree == 0]
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for task_id, task in by_id.items():
            if current in task.get("depends_on", []):
                indegree[task_id] -= 1
                if indegree[task_id] == 0:
                    ready.append(task_id)
    if len(ordered) != len(tasks):
        raise ValueError("delegation plan contains a cycle")

    capability_index = {}
    for profile in worker_capabilities()["capabilities"]:
        for operation in profile["supported_operations"]:
            capability_index.setdefault(operation, []).append(profile["worker_id"])

    results, records = {}, []
    for task_id in ordered:
        task = by_id[task_id]
        dependencies = task.get("depends_on", [])
        if dependencies and results[dependencies[0]]["status"] != "completed":
            records.append({"task_id": task_id, "status": "skipped", "blocked_by": dependencies})
            results[task_id] = records[-1]
            continue
        worker_id = task.get("worker_id")
        eligible = capability_index.get(task["operation"], [])
        if worker_id is None:
            if not eligible:
                raise ValueError("no worker is mapped to the requested operation")
            worker_id = eligible[0]
        if worker_id not in eligible:
            raise PermissionError("selected worker is not authorized for the requested operation")
        task_values = values if not dependencies else _numeric_series(results[dependencies[0]]["result"])
        dispatched = dispatch_worker_task(worker_id, task["operation"], task_values, task.get("params", {}))
        record = {
            "task_id": task_id, "worker_id": worker_id, "operation": task["operation"],
            "depends_on": dependencies, "status": dispatched["status"],
            "result": dispatched.get("result"), "execution_mode": "deterministic_worker_delegation",
        }
        results[task_id] = record
        records.append(record)

    return {
        "status": "completed" if all(item["status"] == "completed" for item in records) else "completed_with_errors",
        "task_count": len(records),
        "completed_count": sum(item["status"] == "completed" for item in records),
        "failed_or_skipped_count": sum(item["status"] != "completed" for item in records),
        "execution_order": ordered,
        "tasks": records,
        "orchestration_mode": "caller_authored_deterministic_dag",
        "research_only": True,
        "limitations": [
            "The caller supplies the task graph; the coordinator does not autonomously plan research.",
            "Worker-to-worker handoff passes a single numeric output series only.",
            "No LLM inference, external data retrieval, forecasts, or order execution occurs.",
        ],
    }
