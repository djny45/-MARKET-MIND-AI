
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter_ns
from typing import Any
import math

from . import indicators

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
):
    """Execute DAG layers; independent nodes may run concurrently when opted in.

    Thread parallelism is configurable because pure-Python CPU work can be
    GIL-bound. Benchmark on the target host before increasing max_workers.
    """
    if not isinstance(max_workers, int) or isinstance(max_workers, bool) or not 1 <= max_workers <= 16:
        raise ValueError("max_workers must be an integer between 1 and 16")
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

    results, node_timings, task_records = {}, {}, {}
    started = perf_counter_ns()
    for layer_index, layer in enumerate(layers):
        tasks = []
        for node_id in layer:
            node = by_id[node_id]
            kind = node.get("type")
            if kind not in NODE_TYPES:
                raise ValueError(f"Unsupported node type: {kind}")
            upstream = [results[source] for source in incoming[node_id]]
            payload = upstream[-1] if upstream else inputs.get(node_id, inputs.get("data", []))
            metadata = node.get("data", {}) or {}
            assigned_worker = metadata.get("workerName") or (
                metadata.get("label") if metadata.get("category") == "worker" else None
            ) or "workflow-engine"
            task_records[node_id] = {
                "task_id": f"task:{node_id}",
                "node_id": node_id,
                "node_type": kind,
                "assigned_worker": str(assigned_worker),
                "dependency_ids": list(incoming[node_id]),
                "layer": layer_index,
                "status": "queued",
                "queued_at_ns": perf_counter_ns(),
            }
            tasks.append((node_id, kind, payload, metadata))

        def run_task(task):
            node_id, kind, payload, params = task
            begin = perf_counter_ns()
            value = _run_node(kind, payload, params)
            end = perf_counter_ns()
            return node_id, value, begin, end

        for node_id, *_ in tasks:
            task_records[node_id]["status"] = "running"
        if max_workers > 1 and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as pool:
                completed = list(pool.map(run_task, tasks))
        else:
            completed = [run_task(task) for task in tasks]
        for node_id, value, task_started_ns, task_completed_ns in completed:
            results[node_id] = value
            elapsed = task_completed_ns - task_started_ns
            node_timings[node_id] = elapsed
            task_records[node_id].update({
                "status": "completed",
                "queue_wait_ns": max(0, task_started_ns - task_records[node_id]["queued_at_ns"]),
                "start_offset_ns": task_started_ns - started,
                "completion_offset_ns": task_completed_ns - started,
                "duration_ns": elapsed,
                "result_key": node_id,
            })

    elapsed = perf_counter_ns() - started
    order = [node_id for layer in layers for node_id in layer]
    tasks_summary = list(task_records.values())
    return {
        "status": "completed",
        "execution_order": order,
        "execution_layers": layers,
        "tasks": tasks_summary,
        "aggregation": {
            "task_count": len(tasks_summary),
            "completed_count": sum(task["status"] == "completed" for task in tasks_summary),
            "failed_count": sum(task["status"] == "failed" for task in tasks_summary),
            "result_count": len(results),
            "result_node_ids": order,
        },
        "results": results,
        "performance": {
            "total_execution_ns": elapsed,
            "node_execution_ns": node_timings,
            "node_count": len(nodes),
            "layer_count": len(layers),
            "max_layer_width": max(map(len, layers), default=0),
            "configured_max_workers": max_workers,
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
        period = max(1, int(params.get("period", 14)))
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
