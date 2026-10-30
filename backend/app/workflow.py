from collections import defaultdict, deque
from typing import Any

NODE_TYPES = {
 "market_input": {"type":"market_input","label":"Market Input","category":"data","inputs":[],"outputs":["data"],"description":"Accept a user-provided market dataset or connector payload."},
 "data_quality": {"type":"data_quality","label":"Data Quality","category":"validation","inputs":["data"],"outputs":["data","quality"],"description":"Check rows, timestamps and numeric values."},
 "sma": {"type":"sma","label":"Moving Average","category":"technical","inputs":["data"],"outputs":["series"],"description":"Calculate a simple moving average."},
 "returns": {"type":"returns","label":"Returns","category":"quant","inputs":["data"],"outputs":["series","summary"],"description":"Calculate period returns and summary statistics."},
 "volatility": {"type":"volatility","label":"Realized Volatility","category":"quant","inputs":["data"],"outputs":["value"],"description":"Estimate standard deviation of returns."},
 "research_summary": {"type":"research_summary","label":"Research Summary","category":"intelligence","inputs":["data"],"outputs":["report"],"description":"Create a deterministic evidence summary."},
}

def _node_id(node):
    return str(node.get("id", ""))

def execute_workflow(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], inputs: dict[str, Any]):
    by_id = {_node_id(n): n for n in nodes}
    if not nodes or any(not k for k in by_id) or len(by_id) != len(nodes):
        raise ValueError("Workflow must contain uniquely identified nodes.")
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    indegree = {k: 0 for k in by_id}
    for edge in edges:
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if source not in by_id or target not in by_id:
            raise ValueError("An edge references a missing node.")
        outgoing[source].append(target)
        incoming[target].append(source)
        indegree[target] += 1
    queue = deque(k for k, degree in indegree.items() if degree == 0)
    order = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for target in outgoing[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(nodes):
        raise ValueError("Workflow contains a cycle. Connect nodes in a directed acyclic graph.")
    results = {}
    for node_id in order:
        node = by_id[node_id]
        kind = node.get("type")
        if kind not in NODE_TYPES:
            raise ValueError(f"Unsupported node type: {kind}")
        params = node.get("data", {}) or {}
        upstream = [results[source] for source in incoming[node_id]]
        payload = upstream[-1] if upstream else inputs.get(node_id, inputs.get("data", []))
        results[node_id] = _run_node(kind, payload, params)
    return {"status":"completed","execution_order":order,"results":results,"research_only":True}

def _numbers(payload):
    if isinstance(payload, dict):
        payload = payload.get("values", payload.get("close", []))
    if not isinstance(payload, list):
        raise ValueError("Expected a list of numeric values or an object with values/close.")
    try:
        return [float(x) for x in payload]
    except (TypeError, ValueError) as exc:
        raise ValueError("Dataset contains non-numeric values.") from exc

def _run_node(kind, payload, params):
    if kind == "market_input":
        return {"values": _numbers(params.get("values", payload))}
    if kind == "data_quality":
        values = _numbers(payload)
        return {"data":{"values":values},"quality":{"rows":len(values),"missing":0,"finite":all(__import__("math").isfinite(x) for x in values),"status":"pass" if values else "empty"}}
    if kind == "sma":
        values = _numbers(payload); period = max(1, int(params.get("period", 20)))
        return {"series":[sum(values[max(0,i-period+1):i+1])/len(values[max(0,i-period+1):i+1]) for i in range(len(values))],"period":period}
    if kind == "returns":
        values = _numbers(payload)
        series = [(values[i]/values[i-1]-1) for i in range(1,len(values)) if values[i-1] != 0]
        return {"series":series,"summary":{"observations":len(series),"mean":sum(series)/len(series) if series else None}}
    if kind == "volatility":
        values = _numbers(payload); rets = [(values[i]/values[i-1]-1) for i in range(1,len(values)) if values[i-1] != 0]
        if len(rets) < 2: return {"value":None,"reason":"At least two returns are required."}
        mean=sum(rets)/len(rets); variance=sum((x-mean)**2 for x in rets)/(len(rets)-1)
        return {"value":variance**0.5,"observations":len(rets),"annualization":"not applied"}
    if kind == "research_summary":
        values = _numbers(payload)
        return {"report":{"observations":len(values),"first":values[0] if values else None,"last":values[-1] if values else None,"scope":"Descriptive calculation only; not a trade recommendation."}}
    raise ValueError(f"No handler for {kind}")
