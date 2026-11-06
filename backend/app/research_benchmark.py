"""Reproducible offline benchmark for research traceability.

This benchmark uses caller-supplied fixtures only. It measures structural citation
coverage, not factual correctness, predictive skill, or market performance.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.research_quality_eval import evaluate_research_draft

MAX_CASES = 100
MAX_CASE_ID_CHARS = 120


def run_offline_research_benchmark(
    cases: list[dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
    regression_threshold: float = 0.05,
) -> dict[str, Any]:
    """Evaluate a bounded, deterministic collection of synthetic research cases."""
    if not isinstance(cases, list) or not cases or len(cases) > MAX_CASES:
        raise ValueError(f"cases must contain 1 to {MAX_CASES} entries")
    if baseline is not None and not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")
    if (isinstance(regression_threshold, bool)
            or not isinstance(regression_threshold, (int, float))
            or not 0 <= regression_threshold <= 1):
        raise ValueError("regression_threshold must be between 0 and 1")

    normalized_cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("benchmark cases must be objects")
        case_id = case.get("case_id")
        if (not isinstance(case_id, str) or not case_id.strip()
                or len(case_id.strip()) > MAX_CASE_ID_CHARS):
            raise ValueError("case_id must contain 1 to 120 characters")
        case_id = case_id.strip()
        if case_id in seen_ids:
            raise ValueError("case_id values must be unique")
        seen_ids.add(case_id)
        normalized_cases.append({
            "case_id": case_id,
            "draft": case.get("draft"),
            "claims": case.get("claims"),
            "source_registry": case.get("source_registry"),
        })

    canonical = json.dumps(
        {"cases": normalized_cases, "baseline": baseline,
         "regression_threshold": regression_threshold},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    benchmark_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    results = []
    for case in normalized_cases:
        evaluation = evaluate_research_draft(
            draft=case["draft"],
            claims=case["claims"],
            source_registry=case["source_registry"],
        )
        results.append({
            "case_id": case["case_id"],
            "evaluation": evaluation,
        })

    metric_keys = ("claim_reference_coverage", "known_source_reference_coverage")
    aggregate = {}
    for key in metric_keys:
        values = [
            result["evaluation"]["metrics"][key]
            for result in results
            if isinstance(result["evaluation"]["metrics"][key], (int, float))
        ]
        aggregate[key] = {
            "mean": round(sum(values) / len(values), 4) if values else None,
            "evaluated_case_count": len(values),
        }

    baseline_comparison = None
    regression_summary = None
    if baseline is not None:
        baseline_metrics = baseline.get("metrics")
        if not isinstance(baseline_metrics, dict):
            raise ValueError("baseline must include a metrics object")
        recognized_metrics = set(metric_keys).intersection(baseline_metrics)
        if not recognized_metrics:
            raise ValueError("baseline metrics must include at least one supported metric")
        for metric_name in recognized_metrics:
            metric_value = baseline_metrics[metric_name]
            if (isinstance(metric_value, bool)
                    or not isinstance(metric_value, (int, float))
                    or not 0 <= metric_value <= 1):
                raise ValueError(
                    f"baseline metric {metric_name} must be a number between 0 and 1"
                )
        baseline_comparison = {}
        regressions = []
        for key in metric_keys:
            current = aggregate[key]["mean"]
            previous = baseline_metrics.get(key)
            if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                delta = round(current - previous, 4)
                baseline_comparison[key] = {
                    "current_mean": current,
                    "baseline_mean": previous,
                    "delta": delta,
                }
                # A zero threshold means "flag any decrease", not "flag a tie".
                if delta < 0 and delta <= -regression_threshold:
                    regressions.append({
                        "metric": key,
                        "delta": delta,
                        "threshold": regression_threshold,
                        "severity": "regression",
                    })
            else:
                baseline_comparison[key] = {
                    "current_mean": current,
                    "baseline_mean": previous,
                    "delta": None,
                }
        regression_summary = {
            "status": "regression_detected" if regressions else "no_regression_detected",
            "threshold": regression_threshold,
            "items": regressions,
            "note": "Flags structural traceability metric drops only; not factual or trading performance.",
        }

    return {
        "benchmark_id": benchmark_id,
        "benchmark_type": "offline_research_traceability",
        "case_count": len(results),
        "aggregate_metrics": aggregate,
        "baseline_comparison": baseline_comparison,
        "regression_summary": regression_summary,
        "case_results": results,
        "limitations": [
            "Uses only the supplied fixture cases; it does not fetch live data.",
            "Measures source-reference structure, not source authenticity or claim entailment.",
            "Does not measure factual accuracy, forecast quality, market performance, or agent intelligence.",
            "Does not trigger trading, agent reassignment, code changes, or deployment.",
        ],
    }
