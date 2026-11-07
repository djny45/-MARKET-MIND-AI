"""Human-reviewed, metrics-only staging experiment records.

This module stores comparisons supplied by a reviewer. It does not execute proposal
code, run benchmarks, modify the agent, train models, deploy, or trade.
"""
from __future__ import annotations

import math
from typing import Any

from .worker_memory import append_memory, read_memory, list_improvement_proposals
from .research_benchmark import run_offline_research_benchmark

_ALLOWED_OUTCOMES = {"candidate_better", "candidate_worse", "no_material_change", "inconclusive"}


def _metrics(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict) or not value or len(value) > 10:
        raise ValueError(f"{label} must contain 1 to 10 numeric metrics")
    result = {}
    for key, number in value.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 100:
            raise ValueError(f"{label} metric names must be non-empty strings up to 100 characters")
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError(f"{label} metrics must be finite numbers")
        result[key.strip()] = float(number)
    return result


def create_staging_experiment(worker_id: str, proposal_memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a comparison record only when proposal's latest review permits staging."""
    if not isinstance(proposal_memory_id, str) or not proposal_memory_id.strip():
        raise ValueError("proposal_memory_id is required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    listing = list_improvement_proposals(worker_id, limit=200)
    proposal = next((item for item in listing["proposals"] if item["memory_id"] == proposal_memory_id), None)
    if proposal is None:
        raise ValueError("proposal was not found for this worker")
    if proposal["review_status"] != "approved_for_staging":
        raise ValueError("proposal must have latest review status approved_for_staging")
    benchmark_id = payload.get("benchmark_id")
    if not isinstance(benchmark_id, str) or not benchmark_id.strip() or len(benchmark_id) > 120:
        raise ValueError("benchmark_id must be a non-empty identifier up to 120 characters")
    reviewer = payload.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError("reviewer must be a non-empty string up to 120 characters")
    notes = payload.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("notes must be a string up to 2000 characters")
    baseline = _metrics(payload.get("baseline_metrics"), "baseline_metrics")
    candidate = _metrics(payload.get("candidate_metrics"), "candidate_metrics")
    common = sorted(set(baseline) & set(candidate))
    if not common:
        raise ValueError("baseline and candidate must share at least one metric")
    comparisons = {key: {"baseline": baseline[key], "candidate": candidate[key],
                         "delta": round(candidate[key] - baseline[key], 8)}
                   for key in common}
    # Metric direction is intentionally not inferred: higher isn't always better.
    outcome = "inconclusive"
    if all(comparisons[key]["delta"] == 0 for key in common):
        outcome = "no_material_change"
    record = {
        "record_type": "staging_experiment_result",
        "proposal_memory_id": proposal_memory_id,
        "benchmark_id": benchmark_id.strip(),
        "reviewer": reviewer.strip(),
        "baseline_metrics": baseline,
        "candidate_metrics": candidate,
        "comparisons": comparisons,
        "outcome": outcome,
        "outcome_note": "Metric direction and practical significance were not inferred; reviewer interpretation required.",
        "notes": notes,
        "execution_mode": "reviewer_supplied_metrics_only",
        "safety_boundary": "no_proposal_code_execution_no_model_update_no_deployment_no_trading",
    }
    return append_memory(worker_id, "validation_result", record,
                         [f"improvement_proposal:{proposal_memory_id}", f"benchmark:{benchmark_id.strip()}"],
                         "unverified")



def run_staging_benchmark(worker_id: str, proposal_memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic offline fixtures as baseline/candidate and persist their metrics."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    baseline_cases = payload.get("baseline_cases")
    candidate_cases = payload.get("candidate_cases")
    reviewer = payload.get("reviewer")
    notes = payload.get("notes", "")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError("reviewer must be a non-empty string up to 120 characters")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("notes must be a string up to 2000 characters")
    baseline_result = run_offline_research_benchmark(baseline_cases)
    candidate_result = run_offline_research_benchmark(candidate_cases)
    metric_names = ("claim_reference_coverage", "known_source_reference_coverage")
    baseline_metrics = {name: baseline_result["aggregate_metrics"][name]["mean"]
                        for name in metric_names}
    candidate_metrics = {name: candidate_result["aggregate_metrics"][name]["mean"]
                         for name in metric_names}
    if any(value is None for value in (*baseline_metrics.values(), *candidate_metrics.values())):
        raise ValueError("all baseline and candidate metrics must be available; provide cases with measurable claims")
    combined_id = f"baseline:{baseline_result['benchmark_id']}|candidate:{candidate_result['benchmark_id']}"
    saved = create_staging_experiment(worker_id, proposal_memory_id, {
        "benchmark_id": combined_id,
        "reviewer": reviewer,
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "notes": notes,
    })
    # Preserve reproducibility metadata on the saved record.
    saved["content"]["benchmark_runs"] = {
        "baseline_benchmark_id": baseline_result["benchmark_id"],
        "candidate_benchmark_id": candidate_result["benchmark_id"],
        "baseline_case_count": baseline_result["case_count"],
        "candidate_case_count": candidate_result["case_count"],
        "benchmark_type": "offline_research_traceability",
        "metric_names": list(metric_names),
    }
    return saved

def list_staging_experiments(worker_id: str, limit: int = 50) -> dict[str, Any]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    records = read_memory(worker_id, "validation_result", limit=200)["memory"]
    experiments = [item for item in records
                   if isinstance(item.get("content"), dict)
                   and item["content"].get("record_type") == "staging_experiment_result"]
    experiments = experiments[:limit]
    return {"worker_id": worker_id, "count": len(experiments), "experiments": experiments,
            "limit": limit, "note": "Append-only reviewer-supplied metrics records; no execution, training, deployment, or trading."}
