"""Bounded worker-to-worker task delegation.

A coordinator routes explicit tasks to existing deterministic worker capabilities.
Dependencies are sequential and values are passed only from completed prior tasks.
No model inference, external data retrieval, or execution is performed.
"""
from .worker_runtime import dispatch_worker_task, worker_capabilities

def delegate_worker_tasks(tasks):
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 50:
        raise ValueError("tasks must contain between 1 and 50 task records")
    capabilities = {item["worker_id"]: set(item["supported_operations"])
                    for item in worker_capabilities()["capabilities"]}
    results, by_id = [], {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError("each task must be an object")
        task_id = task.get("task_id")
        worker_id = task.get("worker_id")
        operation = task.get("operation")
        if not isinstance(task_id, str) or not task_id or task_id in by_id:
            raise ValueError("task_id must be a unique non-empty string")
        if worker_id not in capabilities or operation not in capabilities[worker_id]:
            raise PermissionError(f"worker {worker_id!r} is not authorized for {operation!r}")
        dependency = task.get("depends_on")
        if dependency is not None and dependency not in by_id:
            raise ValueError("depends_on must reference a previously completed task")
        values = task.get("values")
        if dependency is not None:
            prior = by_id[dependency]
            result = prior.get("result")
            if isinstance(result, dict):
                candidate = result.get("values") or result.get("series") or result.get("result")
                if isinstance(candidate, list):
                    values = candidate
            if not isinstance(values, list):
                raise ValueError("dependent task requires a list result from its predecessor")
        if not isinstance(values, list):
            raise ValueError("task values must be a list")
        dispatched = dispatch_worker_task(worker_id, operation, values, task.get("params", {}))
        item = {"task_id": task_id, "depends_on": dependency, "worker_id": worker_id,
                "operation": operation, "status": dispatched["status"],
                "result": dispatched["result"], "execution_mode": "deterministic_worker_delegation"}
        results.append(item)
        by_id[task_id] = item
    return {"delegation_version": "1.0.0", "status": "completed",
            "task_count": len(results), "tasks": results,
            "limitations": ["Tasks execute sequentially in request order.",
                            "Dependencies pass compatible numeric arrays only.",
                            "This is bounded deterministic delegation, not autonomous agent collaboration."],
            "research_only": True}
