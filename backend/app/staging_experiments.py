"""Human-reviewed, metrics-only staging experiment records.

This module stores comparisons supplied by a reviewer. It does not execute proposal
code, run benchmarks, modify the agent, train models, deploy, or trade.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .worker_memory import append_memory, read_memory, list_improvement_proposals
from .research_benchmark import run_offline_research_benchmark
from .research_benchmark_record import serialize_benchmark_record

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
    benchmark_runs = payload.get("benchmark_runs")
    if benchmark_runs is not None:
        if not isinstance(benchmark_runs, dict):
            raise ValueError("benchmark_runs must be an object")
        record["benchmark_runs"] = benchmark_runs
    return append_memory(worker_id, "validation_result", record,
                         [f"improvement_proposal:{proposal_memory_id}", f"benchmark:{benchmark_id.strip()}"],
                         "unverified")




def _paired_case_id_fingerprint(cases: list[dict[str, Any]]) -> str:
    """Return a stable digest of normalized paired case IDs for audit records."""
    case_ids = sorted(case["case_id"].strip() for case in cases)
    canonical = json.dumps(case_ids, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_paired_case_ids(baseline_cases: Any, candidate_cases: Any) -> None:
    """Reject malformed, duplicate, or unpaired fixture IDs before evaluator work."""
    def collect(cases: Any, label: str) -> set[str]:
        if not isinstance(cases, list) or not cases or len(cases) > 100:
            raise ValueError(f"{label} must contain 1 to 100 cases")
        ids: set[str] = set()
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError(f"{label} entries must be objects")
            case_id = case.get("case_id")
            if (not isinstance(case_id, str) or not case_id.strip()
                    or len(case_id.strip()) > 120):
                raise ValueError(f"{label} case_id must contain 1 to 120 characters")
            normalized = case_id.strip()
            if normalized in ids:
                raise ValueError(f"{label} case_id values must be unique")
            ids.add(normalized)
        return ids

    baseline_ids = collect(baseline_cases, "baseline_cases")
    candidate_ids = collect(candidate_cases, "candidate_cases")
    if baseline_ids != candidate_ids:
        raise ValueError("baseline and candidate must use the same case_id values for paired comparison")

def run_staging_benchmark(worker_id: str, proposal_memory_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run paired offline fixtures; optionally evaluate a whitelisted config patch.

    Proposal prose is never interpreted as code or configuration. The optional
    config_patch must be a structured object accepted by the benchmark's explicit
    quality_config whitelist.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    # Check approval before running any evaluator work.
    listing = list_improvement_proposals(worker_id, limit=200)
    proposal = next((item for item in listing["proposals"] if item["memory_id"] == proposal_memory_id), None)
    if proposal is None:
        raise ValueError("proposal was not found for this worker")
    if proposal["review_status"] != "approved_for_staging":
        raise ValueError("proposal must have latest review status approved_for_staging")
    baseline_cases = payload.get("baseline_cases")
    candidate_cases = payload.get("candidate_cases")
    reviewer = payload.get("reviewer")
    notes = payload.get("notes", "")
    config_patch = payload.get("config_patch")
    baseline_fixture_metadata = payload.get("baseline_fixture_metadata")
    candidate_fixture_metadata = payload.get("candidate_fixture_metadata")
    if config_patch is not None and not isinstance(config_patch, dict):
        raise ValueError("config_patch must be a structured object")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError("reviewer must be a non-empty string up to 120 characters")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("notes must be a string up to 2000 characters")
    # Reject malformed or unpaired fixture IDs before any evaluator work.
    _validate_paired_case_ids(baseline_cases, candidate_cases)
    # Baseline uses the default evaluator. Candidate uses only the explicit
    # whitelisted config patch; no proposal text is parsed.
    baseline_result = run_offline_research_benchmark(
        baseline_cases, fixture_metadata=baseline_fixture_metadata
    )
    candidate_result = run_offline_research_benchmark(
        candidate_cases, quality_config=config_patch,
        fixture_metadata=candidate_fixture_metadata,
    )
    metric_names = ("claim_reference_coverage", "known_source_reference_coverage")
    baseline_metrics = {name: baseline_result["aggregate_metrics"][name]["mean"]
                        for name in metric_names}
    candidate_metrics = {name: candidate_result["aggregate_metrics"][name]["mean"]
                         for name in metric_names}
    if any(value is None for value in (*baseline_metrics.values(), *candidate_metrics.values())):
        raise ValueError("all baseline and candidate metrics must be available; provide cases with measurable claims")
    # Require identical case IDs so comparisons are paired, not unrelated samples.
    baseline_by_id = {item['case_id']: item for item in baseline_result['case_results']}
    candidate_by_id = {item['case_id']: item for item in candidate_result['case_results']}
    if set(baseline_by_id) != set(candidate_by_id):
        raise ValueError('baseline and candidate must use the same case_id values for paired comparison')
    paired_metrics = {}
    regressions = []
    for case_id in sorted(baseline_by_id):
        before_metrics = baseline_by_id[case_id]['evaluation']['metrics']
        after_metrics = candidate_by_id[case_id]['evaluation']['metrics']
        case_comparison = {}
        for metric_name in metric_names:
            before = before_metrics.get(metric_name)
            after = after_metrics.get(metric_name)
            if isinstance(before, (int, float)) and not isinstance(before, bool) and isinstance(after, (int, float)) and not isinstance(after, bool):
                delta = round(after - before, 4)
                case_comparison[metric_name] = {'baseline': before, 'candidate': after, 'delta': delta, 'status': 'compared'}
                if delta < 0:
                    regressions.append({'case_id': case_id, 'metric': metric_name, 'delta': delta})
            else:
                case_comparison[metric_name] = {'baseline': before, 'candidate': after, 'delta': None, 'status': 'skipped', 'reason': 'metric_unavailable'}
        paired_metrics[case_id] = case_comparison
    paired_summary = {
        'paired_case_count': len(paired_metrics),
        'regression_count': len(regressions),
        'regressions': regressions,
        'interpretation': 'A decrease in these traceability coverage metrics is a structural regression flag, not evidence of factual, forecast, or trading performance.',
    }
    # Explicit gate for staging eligibility only. It never approves or applies a
    # proposal automatically. Coverage metrics are bounded in [0, 1].
    aggregate_deltas = {
        name: round(candidate_metrics[name] - baseline_metrics[name], 4)
        for name in metric_names
    }
    min_improvement = payload.get("min_improvement", 0.01)
    if (isinstance(min_improvement, bool) or not isinstance(min_improvement, (int, float))
            or not math.isfinite(min_improvement) or not 0 < min_improvement <= 1):
        raise ValueError("min_improvement must be a finite number greater than 0 and at most 1")
    # Case-level drops must not be hidden by aggregate gains on other fixtures.
    has_regression = bool(regressions) or any(delta < 0 for delta in aggregate_deltas.values())
    meaningful_gain = any(delta >= min_improvement for delta in aggregate_deltas.values())
    quality_gate = {
        "status": "blocked_regression" if has_regression else (
            "eligible_for_human_staging_review" if meaningful_gain else "no_meaningful_improvement"
        ),
        "min_improvement": float(min_improvement),
        "aggregate_deltas": aggregate_deltas,
        "automatic_approval": False,
        "note": "Eligibility is a mechanical fixture gate only. Human review is required; it does not establish factual accuracy, predictive skill, or production readiness.",
    }
    # Archive canonical benchmark records and hashes for later verification.
    baseline_record_json = serialize_benchmark_record(baseline_result)
    candidate_record_json = serialize_benchmark_record(candidate_result)
    benchmark_record_evidence = {
        "baseline_record_id": json.loads(baseline_record_json)["record_id"],
        "baseline_record_sha256": hashlib.sha256(baseline_record_json.encode("utf-8")).hexdigest(),
        "candidate_record_id": json.loads(candidate_record_json)["record_id"],
        "candidate_record_sha256": hashlib.sha256(candidate_record_json.encode("utf-8")).hexdigest(),
        "record_schema_version": 1,
        "hash_algorithm": "sha256",
        "note": "Hashes cover canonical serialized benchmark records; fixture provenance remains caller-declared.",
    }
    combined_id = f"baseline:{baseline_result['benchmark_id']}|candidate:{candidate_result['benchmark_id']}"
    saved = create_staging_experiment(worker_id, proposal_memory_id, {
        "benchmark_id": combined_id,
        "reviewer": reviewer,
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "notes": notes,
        "benchmark_runs": {
            "baseline_benchmark_id": baseline_result["benchmark_id"],
            "candidate_benchmark_id": candidate_result["benchmark_id"],
            "benchmark_record_evidence": benchmark_record_evidence,
            "baseline_case_count": baseline_result["case_count"],
            "candidate_case_count": candidate_result["case_count"],
            "paired_case_id_sha256": _paired_case_id_fingerprint(baseline_cases),
            "paired_case_id_fingerprint_note": (
                "Digest covers normalized case IDs only; benchmark IDs separately fingerprint "
                "the evaluator inputs/configuration. Neither digest verifies dataset provenance."
            ),
            "baseline_fixture_overlap": {
                "pair_count_flagged": baseline_result["fixture_overlap"]["pair_count_flagged"],
                "threshold": baseline_result["fixture_overlap"]["threshold"],
                "method": baseline_result["fixture_overlap"]["method"],
            },
            "candidate_fixture_overlap": {
                "pair_count_flagged": candidate_result["fixture_overlap"]["pair_count_flagged"],
                "threshold": candidate_result["fixture_overlap"]["threshold"],
                "method": candidate_result["fixture_overlap"]["method"],
            },
            "benchmark_type": "offline_research_traceability",
            "evaluator_version": baseline_result["evaluator_version"],
            "baseline_provenance": {
                "fixture_origin": baseline_result["fixture_origin"],
                "fixture_metadata": baseline_result["fixture_metadata"],
                "provenance_note": baseline_result["provenance_note"],
            },
            "candidate_provenance": {
                "fixture_origin": candidate_result["fixture_origin"],
                "fixture_metadata": candidate_result["fixture_metadata"],
                "provenance_note": candidate_result["provenance_note"],
            },
            "config_patch": candidate_result["quality_config"],
            "config_patch_mode": "whitelisted_evaluator_config_only",
            "quality_gate": quality_gate,
            "metric_names": list(metric_names),
            "paired_case_metrics": paired_metrics,
            "paired_case_summary": paired_summary,
        },
    })
    return saved

def summarize_staging_experiments(worker_id: str, limit: int = 100) -> dict[str, Any]:
    """Summarize recent append-only experiments without ranking strategies or implying significance."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    records = read_memory(worker_id, "validation_result", limit=200)["memory"]
    experiments = [item for item in records
                   if isinstance(item.get("content"), dict)
                   and item["content"].get("record_type") == "staging_experiment_result"][:limit]
    gate_counts: dict[str, int] = {}
    proposal_counts: dict[str, int] = {}
    metric_deltas: dict[str, list[float]] = {}
    configs: dict[str, int] = {}
    for item in experiments:
        content = item["content"]
        proposal_id = content.get("proposal_memory_id", "unknown")
        proposal_counts[proposal_id] = proposal_counts.get(proposal_id, 0) + 1
        runs = content.get("benchmark_runs", {})
        gate = runs.get("quality_gate", {}) if isinstance(runs, dict) else {}
        gate_status = gate.get("status", "not_available")
        gate_counts[gate_status] = gate_counts.get(gate_status, 0) + 1
        for name, delta in gate.get("aggregate_deltas", {}).items():
            if isinstance(delta, (int, float)) and not isinstance(delta, bool) and math.isfinite(delta):
                metric_deltas.setdefault(name, []).append(float(delta))
        patch = runs.get("config_patch") if isinstance(runs, dict) else None
        if isinstance(patch, dict):
            config_key = str(sorted(patch.items()))
            configs[config_key] = configs.get(config_key, 0) + 1
    metric_summary = {
        name: {
            "observations": len(values),
            "mean_delta": round(sum(values) / len(values), 4),
            "min_delta": round(min(values), 4),
            "max_delta": round(max(values), 4),
        }
        for name, values in metric_deltas.items() if values
    }
    return {
        "worker_id": worker_id,
        "experiment_count": len(experiments),
        "proposal_experiment_counts": proposal_counts,
        "quality_gate_status_counts": gate_counts,
        "metric_delta_summary": metric_summary,
        "config_patch_frequency": configs,
        "interpretation": "Descriptive summaries of recent fixture runs only. No statistical significance, causal attribution, market skill, or strategy ranking is inferred.",
        "limit": limit,
    }


def summarize_repeatability(worker_id: str, limit: int = 200, min_trials: int = 3) -> dict[str, Any]:
    """Report repeated identical fixture/config comparisons; descriptive, not inferential."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if not isinstance(min_trials, int) or isinstance(min_trials, bool) or not 2 <= min_trials <= 20:
        raise ValueError("min_trials must be between 2 and 20")
    records = read_memory(worker_id, "validation_result", limit=200)["memory"]
    experiments = [item for item in records
                   if isinstance(item.get("content"), dict)
                   and item["content"].get("record_type") == "staging_experiment_result"][:limit]
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in experiments:
        content = item["content"]
        runs = content.get("benchmark_runs")
        if not isinstance(runs, dict):
            continue
        baseline_id = runs.get("baseline_benchmark_id")
        candidate_id = runs.get("candidate_benchmark_id")
        patch = runs.get("config_patch", {})
        if not isinstance(baseline_id, str) or not isinstance(candidate_id, str) or not isinstance(patch, dict):
            continue
        # Same proposal, exact baseline/candidate fixture fingerprints, and config.
        # Use canonical JSON rather than repr/sorted top-level items so nested
        # config objects compare deterministically.
        import json
        config_repr = json.dumps(patch, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        key = (str(content.get("proposal_memory_id", "")),
               baseline_id + "|" + candidate_id,
               config_repr)
        gate = runs.get("quality_gate", {})
        groups.setdefault(key, []).append({
            "gate_status": gate.get("status", "not_available") if isinstance(gate, dict) else "not_available",
            "deltas": gate.get("aggregate_deltas", {}) if isinstance(gate, dict) else {},
            "record_id": item.get("memory_id"),
        })
    repeated = []
    insufficient = 0
    for (proposal_id, fingerprint_pair, config_repr), trials in groups.items():
        if len(trials) < min_trials:
            insufficient += 1
            continue
        statuses: dict[str, int] = {}
        metric_signs: dict[str, dict[str, int]] = {}
        for trial in trials:
            status = trial["gate_status"]
            statuses[status] = statuses.get(status, 0) + 1
            for metric, delta in trial["deltas"].items():
                if isinstance(delta, (int, float)) and not isinstance(delta, bool) and math.isfinite(delta):
                    sign = "positive" if delta > 0 else "negative" if delta < 0 else "zero"
                    metric_signs.setdefault(metric, {"positive": 0, "negative": 0, "zero": 0})[sign] += 1
        repeated.append({
            "proposal_memory_id": proposal_id,
            "benchmark_fingerprint_pair": fingerprint_pair,
            "config_patch_key": config_repr,
            "trial_count": len(trials),
            "gate_status_counts": statuses,
            "metric_delta_sign_counts": metric_signs,
            "consistency_label": "uniform_gate_status" if len(statuses) == 1 else "mixed_gate_status",
        })
    return {
        "worker_id": worker_id,
        "groups_meeting_min_trials": len(repeated),
        "groups_below_min_trials": insufficient,
        "min_trials": min_trials,
        "repeatability_groups": repeated,
        "interpretation": "Exact fixture/config repeats only. Status/sign consistency is descriptive; it is not statistical significance, independent-data validation, causality, or evidence of market/trading performance.",
        "limit": limit,
    }


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

def summarize_staging_provenance(worker_id: str, limit: int = 100) -> dict[str, Any]:
    """Audit declared fixture provenance across stored staging benchmark records."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    records = read_memory(worker_id, "validation_result", limit=200)["memory"]
    experiments = [
        item for item in records
        if isinstance(item.get("content"), dict)
        and item["content"].get("record_type") == "staging_experiment_result"
        and isinstance(item["content"].get("benchmark_runs"), dict)
        and "baseline_benchmark_id" in item["content"].get("benchmark_runs", {})
    ][:limit]
    missing_counts = {
        "baseline_fixture_metadata_missing": 0, "candidate_fixture_metadata_missing": 0,
        "baseline_dataset_name_missing": 0, "candidate_dataset_name_missing": 0,
        "baseline_dataset_version_missing": 0, "candidate_dataset_version_missing": 0,
    }
    audit_records = []
    for item in experiments:
        content = item["content"]
        runs = content["benchmark_runs"]
        base = runs.get("baseline_provenance", {})
        candidate = runs.get("candidate_provenance", {})
        base = base if isinstance(base, dict) else {}
        candidate = candidate if isinstance(candidate, dict) else {}
        base_meta = base.get("fixture_metadata", {})
        candidate_meta = candidate.get("fixture_metadata", {})
        base_meta = base_meta if isinstance(base_meta, dict) else {}
        candidate_meta = candidate_meta if isinstance(candidate_meta, dict) else {}
        checks = (
            ("baseline_fixture_metadata_missing", bool(base_meta)),
            ("candidate_fixture_metadata_missing", bool(candidate_meta)),
            ("baseline_dataset_name_missing", bool(base_meta.get("dataset_name"))),
            ("candidate_dataset_name_missing", bool(candidate_meta.get("dataset_name"))),
            ("baseline_dataset_version_missing", bool(base_meta.get("dataset_version"))),
            ("candidate_dataset_version_missing", bool(candidate_meta.get("dataset_version"))),
        )
        for key, present in checks:
            if not present:
                missing_counts[key] += 1
        audit_records.append({
            "memory_id": item.get("memory_id"),
            "proposal_memory_id": content.get("proposal_memory_id"),
            "benchmark_id": content.get("benchmark_id"),
            "evaluator_version": runs.get("evaluator_version"),
            "baseline": {"benchmark_id": runs.get("baseline_benchmark_id"),
                         "fixture_origin": base.get("fixture_origin", "legacy_or_missing"),
                         "fixture_metadata": base_meta, "metadata_present": bool(base_meta)},
            "candidate": {"benchmark_id": runs.get("candidate_benchmark_id"),
                          "fixture_origin": candidate.get("fixture_origin", "legacy_or_missing"),
                          "fixture_metadata": candidate_meta, "metadata_present": bool(candidate_meta)},
        })
    return {
        "worker_id": worker_id, "record_count": len(audit_records),
        "records": audit_records, "missing_provenance_counts": missing_counts,
        "interpretation": "Audits caller-declared metadata only. Missing labels do not prove bad data; present labels do not authenticate sources. Older records may predate provenance fields.",
        "limit": limit,
    }


def summarize_research_quality_dashboard(worker_id: str, limit: int = 100) -> dict[str, Any]:
    """Combine recent staging gate, regression, provenance, and repeatability signals.

    This is a bounded descriptive dashboard over saved offline fixture experiments.
    It does not validate source authenticity, factual correctness, predictive skill,
    or trading performance.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    records = read_memory(worker_id, "validation_result", limit=200)["memory"]
    experiments = [
        item for item in records
        if isinstance(item.get("content"), dict)
        and item["content"].get("record_type") == "staging_experiment_result"
    ][:limit]
    gate_counts: dict[str, int] = {}
    delta_values: dict[str, list[float]] = {}
    provenance_missing = {
        "baseline_metadata_missing": 0, "candidate_metadata_missing": 0,
        "baseline_dataset_name_missing": 0, "candidate_dataset_name_missing": 0,
        "baseline_dataset_version_missing": 0, "candidate_dataset_version_missing": 0,
    }
    regression_experiment_count = 0
    paired_regression_total = 0
    experiments_missing_dataset_name_or_version = 0
    overlap_flagged_pairs_total = 0
    experiments_with_overlap_flags = 0
    dashboard_records = []
    for item in experiments:
        content = item["content"]
        runs = content.get("benchmark_runs", {})
        runs = runs if isinstance(runs, dict) else {}
        gate = runs.get("quality_gate", {})
        gate = gate if isinstance(gate, dict) else {}
        status = gate.get("status", "not_available")
        gate_counts[status] = gate_counts.get(status, 0) + 1
        paired = runs.get("paired_case_summary", {})
        paired = paired if isinstance(paired, dict) else {}
        regression_count = paired.get("regression_count", 0)
        if isinstance(regression_count, int) and not isinstance(regression_count, bool) and regression_count >= 0:
            paired_regression_total += regression_count
            if regression_count:
                regression_experiment_count += 1
        base = runs.get("baseline_provenance", {})
        candidate = runs.get("candidate_provenance", {})
        base = base if isinstance(base, dict) else {}
        candidate = candidate if isinstance(candidate, dict) else {}
        base_meta = base.get("fixture_metadata", {})
        candidate_meta = candidate.get("fixture_metadata", {})
        base_meta = base_meta if isinstance(base_meta, dict) else {}
        candidate_meta = candidate_meta if isinstance(candidate_meta, dict) else {}
        checks = {
            "baseline_metadata_missing": bool(base_meta),
            "candidate_metadata_missing": bool(candidate_meta),
            "baseline_dataset_name_missing": bool(base_meta.get("dataset_name")),
            "candidate_dataset_name_missing": bool(candidate_meta.get("dataset_name")),
            "baseline_dataset_version_missing": bool(base_meta.get("dataset_version")),
            "candidate_dataset_version_missing": bool(candidate_meta.get("dataset_version")),
        }
        for key, present in checks.items():
            if not present:
                provenance_missing[key] += 1
        if not all(checks[key] for key in (
            "baseline_dataset_name_missing", "candidate_dataset_name_missing",
            "baseline_dataset_version_missing", "candidate_dataset_version_missing",
        )):
            experiments_missing_dataset_name_or_version += 1
        baseline_overlap = runs.get("baseline_fixture_overlap", {})
        candidate_overlap = runs.get("candidate_fixture_overlap", {})
        baseline_overlap = baseline_overlap if isinstance(baseline_overlap, dict) else {}
        candidate_overlap = candidate_overlap if isinstance(candidate_overlap, dict) else {}
        overlap_pair_count = 0
        for overlap in (baseline_overlap, candidate_overlap):
            count = overlap.get("pair_count_flagged", 0)
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                overlap_pair_count += count
        overlap_flagged_pairs_total += overlap_pair_count
        if overlap_pair_count:
            experiments_with_overlap_flags += 1
        aggregate_deltas = gate.get("aggregate_deltas", {})
        aggregate_deltas = aggregate_deltas if isinstance(aggregate_deltas, dict) else {}
        for metric_name, delta in aggregate_deltas.items():
            if (isinstance(metric_name, str) and isinstance(delta, (int, float))
                    and not isinstance(delta, bool) and math.isfinite(delta)):
                delta_values.setdefault(metric_name, []).append(float(delta))
        dashboard_records.append({
            "memory_id": item.get("memory_id"),
            "proposal_memory_id": content.get("proposal_memory_id"),
            "benchmark_id": content.get("benchmark_id"),
            "quality_gate_status": status,
            "aggregate_deltas": gate.get("aggregate_deltas", {}),
            "paired_case_count": paired.get("paired_case_count", 0),
            "paired_regression_count": regression_count,
            "fixture_overlap_flagged_pair_count": overlap_pair_count,
            "evaluator_version": runs.get("evaluator_version"),
            "baseline_dataset": base_meta.get("dataset_name"),
            "candidate_dataset": candidate_meta.get("dataset_name"),
            "baseline_dataset_version": base_meta.get("dataset_version"),
            "candidate_dataset_version": candidate_meta.get("dataset_version"),
        })
    delta_summary = {
        metric: {
            "observations": len(values),
            "mean_delta": round(sum(values) / len(values), 4),
            "min_delta": round(min(values), 4),
            "max_delta": round(max(values), 4),
            "negative_count": sum(value < 0 for value in values),
            "zero_count": sum(value == 0 for value in values),
            "positive_count": sum(value > 0 for value in values),
        }
        for metric, values in delta_values.items() if values
    }
    repeatability = summarize_repeatability(worker_id, limit=limit, min_trials=3)
    return {
        "worker_id": worker_id,
        "experiment_count": len(dashboard_records),
        "quality_gate_status_counts": gate_counts,
        "experiments_with_paired_regressions": regression_experiment_count,
        "experiments_missing_dataset_name_or_version": experiments_missing_dataset_name_or_version,
        "paired_regression_total": paired_regression_total,
        "experiments_with_fixture_overlap_flags": experiments_with_overlap_flags,
        "fixture_overlap_flagged_pair_total": overlap_flagged_pairs_total,
        "aggregate_delta_summary": delta_summary,
        "provenance_missing_counts": provenance_missing,
        "repeatability": {
            "groups_meeting_min_trials": repeatability["groups_meeting_min_trials"],
            "groups_below_min_trials": repeatability["groups_below_min_trials"],
            "min_trials": repeatability["min_trials"],
        },
        "experiments": dashboard_records,
        "limit": limit,
        "interpretation": "Descriptive audit of saved offline fixture experiments. Provenance is caller-declared; repeatability uses exact fixture/config repeats. This dashboard does not validate truth, source independence, predictive skill, or trading performance.",
    }
