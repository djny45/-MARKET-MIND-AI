"""Reproducible local benchmark for sequential vs concurrent DAG scheduling.

Run from repository root:
  PYTHONPATH=backend python backend/benchmarks/benchmark_workflow.py --samples 5000 --repeats 15

This measures workflow execution on the current host; it is not a production SLA.
"""
import argparse
import json
import platform
import statistics
import sys
from time import perf_counter_ns

from app.workflow import execute_workflow


def percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[index]


def make_workflow(samples, branches):
    values = [100.0 + ((index * 17) % 101) / 10 for index in range(samples)]
    nodes = [{"id": "feed", "type": "market_input", "data": {"values": values}}]
    edges = []
    kinds = ("sma", "ema", "rsi", "macd", "bollinger", "returns", "volatility")
    for index in range(branches):
        node_id = f"analysis_{index:02d}"
        nodes.append({
            "id": node_id,
            "type": kinds[index % len(kinds)],
            "data": {"period": 14},
        })
        edges.append({"source": "feed", "target": node_id})
    return nodes, edges


def measure(nodes, edges, repeats, workers):
    timings = []
    for _ in range(repeats):
        start = perf_counter_ns()
        result = execute_workflow(nodes, edges, {}, max_workers=workers)
        timings.append(perf_counter_ns() - start)
        if result["status"] != "completed":
            raise RuntimeError("Workflow did not complete")
    return {
        "configured_workers": workers,
        "runs": repeats,
        "median_ms": round(statistics.median(timings) / 1_000_000, 3),
        "p95_ms": round(percentile(timings, 0.95) / 1_000_000, 3),
        "min_ms": round(min(timings) / 1_000_000, 3),
        "max_ms": round(max(timings) / 1_000_000, 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--branches", type=int, default=7)
    parser.add_argument("--repeats", type=int, default=15)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    args = parser.parse_args()
    if args.samples < 20 or args.branches < 2 or args.repeats < 3:
        parser.error("samples >= 20, branches >= 2 and repeats >= 3 are required")
    if any(worker < 1 or worker > 16 for worker in args.workers):
        parser.error("worker counts must be between 1 and 16")

    nodes, edges = make_workflow(args.samples, args.branches)
    # Warm each configured mode before collecting timings.
    for workers in dict.fromkeys(args.workers):
        execute_workflow(nodes, edges, {}, max_workers=workers)
    results = [measure(nodes, edges, args.repeats, workers)
               for workers in dict.fromkeys(args.workers)]
    baseline = next((item["median_ms"] for item in results
                     if item["configured_workers"] == 1), None)
    for item in results:
        item["speedup_vs_single"] = (
            round(baseline / item["median_ms"], 3)
            if baseline and item["median_ms"] else None
        )
    print(json.dumps({
        "benchmark": "market_mind_workflow_scheduler",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or "not reported",
        },
        "workload": {
            "samples_per_branch": args.samples,
            "independent_branches": args.branches,
            "repeats": args.repeats,
        },
        "results": results,
        "interpretation": "Host-specific measurements; compare only on the same machine and workload. Threading may be slower for GIL-bound Python calculations.",
    }, indent=2))


if __name__ == "__main__":
    main()
