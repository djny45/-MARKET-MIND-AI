
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter_ns
from typing import Any
import math

from . import indicators
from .worker_runtime import assign_worker
from .worker_contracts import (
    get_worker_contract, validate_worker_input, validate_worker_output,
    validate_evidence_provenance,
)

NODE_TYPES = {
 "market_input":{"type":"market_input","label":"Market Input","category":"data","inputs":[],"outputs":["data"],"description":"Accept normalized numeric observations."},
 "data_quality":{"type":"data_quality","label":"Data Quality","category":"validation","inputs":["data"],"outputs":["data","quality"],"description":"Validate numeric observations."},
 "sma":{"type":"sma","label":"Simple Moving Average","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate SMA."},
 "ema":{"type":"ema","label":"Exponential Moving Average","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate EMA."},
 "rsi":{"type":"rsi","label":"Relative Strength Index","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate RSI."},
 "macd":{"type":"macd","label":"MACD","category":"technical","inputs":["data"],"outputs":["macd","signal","histogram"],"description":"Calculate MACD line, signal and histogram."},
 "bollinger":{"type":"bollinger","label":"Bollinger Bands","category":"technical","inputs":["data"],"outputs":["middle","upper","lower"],"description":"Calculate Bollinger bands."},
 "returns":{"type":"returns","label":"Returns","category":"quant","inputs":["data"],"outputs":["series","summary"],"description":"Calculate simple period returns."},
 "volatility":{"type":"volatility","label":"Realized Volatility","category":"quant","inputs":["data"],"outputs":["value"],"description":"Estimate sample volatility of returns."},
 "research_summary":{"type":"research_summary","label":"Research Summary","category":"intelligence","inputs":["data"],"outputs":["report"],"description":"Create a descriptive evidence summary."},
}


def _node_id(node):
    return str(node.get("id", ""))


def execute_workflow(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    inputs: dict[str, Any],
    max_workers: int = 1,
    max_retries: int = 0,
    checkpoint_callback=None,
    initial_checkpoint: dict[str, Any] | None = None,
):
    """Execute DAG layers; independent nodes may run concurrently when opted in.

    Thread parallelism is configurable because pure-Python CPU work can be
    GIL-bound. Benchmark on the target host before increasing max_workers.
    """
    if not isinstance(max_workers, int) or isinstance(max_workers, bool) or not 1 <= max_workers <= 16:
        raise ValueError("max_workers must be an integer between 1 and 16")
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 0 <= max_retries <= 3:
        raise ValueError("max_retries must be an integer between 0 and 3")
    by_id = {_node_id(node): node for node in nodes}
    if not nodes or any(not key for key in by_id) or len(by_id) != len(nodes):
        raise ValueError("Workflow must contain uniquely identified nodes.")

    incoming, outgoing = defaultdict(list), defaultdict(list)
    indegree = {key: 0 for key in by_id}
    for edge in edges:
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if source not in by_id or target not in by_id:
            raise ValueError("An edge references a missing node.")
        outgoing[source].append(target)
        incoming[target].append(source)
        indegree[target] += 1

    ready = deque(key for key, degree in indegree.items() if degree == 0)
    layers, visited = [], 0
    while ready:
        layer = list(ready)
        ready.clear()
        layers.append(layer)
        visited += len(layer)
        for current in layer:
            for target in outgoing[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
    if visited != len(nodes):
        raise ValueError("Workflow contains a cycle.")

    checkpoint = initial_checkpoint if initial_checkpoint is not None else {}
    if not isinstance(checkpoint, dict):
        raise ValueError("initial_checkpoint must be an object")
    completed_ids = checkpoint.get("completed_node_ids", [])
    checkpoint_results = checkpoint.get("results", {})
    checkpoint_tasks = checkpoint.get("tasks", {})
    if (not isinstance(completed_ids, list)
            or any(not isinstance(item, str) for item in completed_ids)
            or len(set(completed_ids)) != len(completed_ids)):
        raise ValueError("checkpoint completed_node_ids must be a unique list of node IDs")
    if not isinstance(checkpoint_results, dict) or not isinstance(checkpoint_tasks, dict):
        raise ValueError("checkpoint results and tasks must be objects")
    completed_before = set(completed_ids)
    if not completed_before.issubset(by_id):
        raise ValueError("checkpoint contains unknown completed node IDs")
    if not set(checkpoint_results).issubset(by_id) or not set(checkpoint_tasks).issubset(by_id):
        raise ValueError("checkpoint contains unknown result or task node IDs")
    for completed_id in completed_before:
        task = checkpoint_tasks.get(completed_id)
        expected_type = by_id[completed_id].get("type")
        if (completed_id not in checkpoint_results or not isinstance(task, dict)
                or task.get("status") != "completed"
                or task.get("node_id", completed_id) != completed_id
                or task.get("node_type") != expected_type):
            raise ValueError("checkpoint completed nodes require a matching completed task and result")
        if expected_type not in NODE_TYPES:
            raise ValueError(f"Unsupported node type in checkpoint: {expected_type}")
        try:
            validate_worker_output(expected_type, checkpoint_results[completed_id])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"checkpoint result for node {completed_id} violates its worker contract: {exc}"
            ) from exc
    if set(checkpoint_results) != completed_before:
        raise ValueError("checkpoint results must match completed_node_ids")
    results = dict(checkpoint_results)
    task_records = dict(checkpoint_tasks)
    node_timings = {
        key: item.get("duration_ns", 0)
        for key, item in task_records.items()
        if item.get("status") == "completed"
    }
    started = perf_counter_ns()
    for layer_index, layer in enumerate(layers):
        tasks = []
        for node_id in layer:
            if node_id in completed_before and task_records.get(node_id, {}).get("status") == "completed":
                continue
            node = by_id[node_id]
            kind = node.get("type")
            if kind not in NODE_TYPES:
                raise ValueError(f"Unsupported node type: {kind}")
            dependencies = list(incoming[node_id])
            metadata = node.get("data", {}) or {}
            worker_assignment = assign_worker(kind, metadata.get("worker_id"))
            assigned_worker = metadata.get("workerName") or (
                metadata.get("label") if metadata.get("category") == "worker" else None
            ) or worker_assignment["worker_name"]
            task_records[node_id] = {
                "task_id": f"task:{node_id}",
                "node_id": node_id,
                "node_type": kind,
                "assigned_worker": str(assigned_worker),
                "assigned_worker_id": worker_assignment["worker_id"],
                "worker_department": worker_assignment["department"],
                "worker_specialty": worker_assignment["specialty"],
                "intelligence_core": worker_assignment["intelligence_core"],
                "execution_mode": worker_assignment["execution_mode"],
                "worker_contract": get_worker_contract(kind),
                "evidence_status": "not_supplied",
                "dependency_ids": dependencies,
                "layer": layer_index,
                "status": "queued",
                "attempts": 0,
                "queued_at_ns": perf_counter_ns(),
            }
            failed_dependencies = [
                dep for dep in dependencies
                if task_records.get(dep, {}).get("status") != "completed"
            ]
            if failed_dependencies:
                task_records[node_id].update({
                    "status": "skipped",
                    "error_type": "DependencyFailure",
                    "error": "Skipped because dependencies did not complete.",
                    "blocked_by": failed_dependencies,
                    "queue_wait_ns": 0,
                    "duration_ns": 0,
                })
                continue
            upstream = [results[source] for source in dependencies]
            payload = upstream[-1] if upstream else inputs.get(node_id, inputs.get("data", []))
            tasks.append((node_id, kind, payload, metadata))

        def run_task(task):
            node_id, kind, payload, params = task
            record = task_records[node_id]
            record["status"] = "running"
            last_error = None
            for attempt in range(1, max_retries + 2):
                begin = perf_counter_ns()
                record["attempts"] = attempt
                try:
                    evidence = params.get("evidence")
                    if evidence is None and isinstance(payload, dict):
                        evidence = payload.get("evidence")
                    if evidence is not None:
                        validate_evidence_provenance(evidence)
                        record["evidence_status"] = "validated_input_provenance"
                        record["evidence_provenance"] = {
                            key: evidence[key]
                            for key in ("input_source", "retrieval_timestamp", "quality_status")
                        }
                    validate_worker_input(kind, params.get("values", payload) if kind == "market_input" else payload)
                    value = _run_node(kind, payload, params)
                    validate_worker_output(kind, value)
                    end = perf_counter_ns()
                    return node_id, value, begin, end, None
                except Exception as exc:
                    end = perf_counter_ns()
                    last_error = {
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                        "failed_attempt_duration_ns": end - begin,
                    }
            return node_id, None, begin, end, last_error

        if max_workers > 1 and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as pool:
                completed = list(pool.map(run_task, tasks))
        else:
            completed = [run_task(task) for task in tasks]
        for node_id, value, task_started_ns, task_completed_ns, error in completed:
            record = task_records[node_id]
            elapsed = task_completed_ns - task_started_ns
            node_timings[node_id] = elapsed
            record.update({
                "queue_wait_ns": max(0, task_started_ns - record["queued_at_ns"]),
                "start_offset_ns": task_started_ns - started,
                "completion_offset_ns": task_completed_ns - started,
                "duration_ns": elapsed,
            })
            if error:
                record.update({"status": "failed", **error})
            else:
                results[node_id] = value
                record.update({"status": "completed", "result_key": node_id})
        if checkpoint_callback is not None:
            checkpoint_callback({
                "completed_node_ids": [key for key, item in task_records.items() if item["status"] == "completed"],
                "results": results,
                "tasks": task_records,
                "completed_layers": layer_index + 1,
            })

    elapsed = perf_counter_ns() - started
    order = [node_id for layer in layers for node_id in layer]
    tasks_summary = list(task_records.values())
    completed_count = sum(task["status"] == "completed" for task in tasks_summary)
    failed_count = sum(task["status"] == "failed" for task in tasks_summary)
    skipped_count = sum(task["status"] == "skipped" for task in tasks_summary)
    return {
        "status": "completed" if not failed_count and not skipped_count else "completed_with_errors",
        "execution_order": order,
        "execution_layers": layers,
        "tasks": tasks_summary,
        "aggregation": {
            "task_count": len(tasks_summary),
            "completed_count": completed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "result_count": len(results),
            "result_node_ids": [node_id for node_id in order if node_id in results],
        },
        "results": results,
        "performance": {
            "total_execution_ns": elapsed,
            "node_execution_ns": node_timings,
            "node_count": len(nodes),
            "layer_count": len(layers),
            "max_layer_width": max(map(len, layers), default=0),
            "configured_max_workers": max_workers,
            "configured_max_retries": max_retries,
            "parallelism_used": max_workers > 1 and any(len(layer) > 1 for layer in layers),
            "clock": "process_monotonic",
        },
        "research_only": True,
    }

def _numbers(payload):
    if isinstance(payload, dict):
        for key in ("values", "close", "series"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            if isinstance(payload.get("data"), dict):
                return _numbers(payload["data"])
            if isinstance(payload.get("value"), (int, float)):
                payload = [payload["value"]]
            else:
                raise ValueError("Expected numeric values, close or series.")
    if not isinstance(payload, list):
        raise ValueError("Expected a list of numeric values.")
    try:
        values = [float(value) for value in payload]
    except (TypeError, ValueError) as exc:
        raise ValueError("Dataset contains non-numeric values.") from exc
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Dataset contains non-finite values.")
    return values


def _run_node(kind, payload, params):
    if kind == "market_input":
        return {"values": _numbers(params.get("values", payload))}
    if kind == "data_quality":
        values = _numbers(payload)
        return {"data": {"values": values}, "quality": {
            "rows": len(values), "missing": 0, "finite": True,
            "status": "pass" if values else "empty",
        }}
    if kind in ("sma", "ema", "rsi", "macd", "bollinger"):
        values = _numbers(payload)
        period = params.get("period", 14)
        if isinstance(period, bool) or not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")
        if kind == "sma":
            return {"series": indicators.sma(values, period), "period": period}
        if kind == "ema":
            return {"series": indicators.ema(values, period), "period": period}
        if kind == "rsi":
            return {"series": indicators.rsi(values, period), "period": period}
        if kind == "macd":
            return indicators.macd(values)
        return indicators.bollinger(values, period)
    if kind == "returns":
        values = _numbers(payload)
        series = indicators.returns(values)
        return {"series": series, "summary": {
            "observations": len(series),
            "mean": sum(series) / len(series) if series else None,
        }}
    if kind == "volatility":
        return indicators.realized_volatility(_numbers(payload))
    if kind == "research_summary":
        values = _numbers(payload)
        return {"report": {
            "observations": len(values),
            "first": values[0] if values else None,
            "last": values[-1] if values else None,
            "scope": "Descriptive calculations only; not a trade recommendation.",
        }}
    raise ValueError(f"No handler for {kind}")
