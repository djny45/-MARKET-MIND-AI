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
BASELINE_METRICS = ("claim_reference_coverage", "known_source_reference_coverage", "uncertainty_marker_coverage")
DEFAULT_QUALITY_CONFIG = {"uncertainty_markers": ["uncertain", "unknown", "limitation", "assumption", "not verified", "cannot conclude", "insufficient data"]}
MAX_CONFIG_MARKERS = 20
BENCHMARK_EVALUATOR_VERSION = "research-traceability-v1"
FIXTURE_METADATA_FIELDS = {"dataset_name", "dataset_version", "source_description", "prepared_by", "collection_date"}
MAX_FIXTURE_METADATA_VALUE_CHARS = 160


def _validate_fixture_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    """Normalize bounded caller-declared provenance; values are not independently verified."""
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("fixture_metadata must be an object")
    unknown = set(metadata) - FIXTURE_METADATA_FIELDS
    if unknown:
        raise ValueError(f"fixture_metadata contains unsupported fields: {sorted(unknown)}")
    normalized = {}
    for key, value in metadata.items():
        if not isinstance(value, str) or len(value.strip()) > MAX_FIXTURE_METADATA_VALUE_CHARS:
            raise ValueError(f"fixture_metadata.{key} must be a string up to {MAX_FIXTURE_METADATA_VALUE_CHARS} characters")
        if value.strip():
            normalized[key] = value.strip()
    return normalized


def _validate_baseline_metrics(baseline: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate baseline schema before evaluating any benchmark cases."""
    if baseline is None:
        return None
    metrics = baseline.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("baseline must include a metrics object")
    unknown_metrics = set(metrics) - set(BASELINE_METRICS)
    if unknown_metrics:
        raise ValueError(
            f"baseline contains unsupported metrics: {sorted(unknown_metrics)}"
        )
    if not metrics:
        raise ValueError("baseline metrics must include at least one supported metric")
    for metric_name, metric_value in metrics.items():
        if (isinstance(metric_value, bool)
                or not isinstance(metric_value, (int, float))
                or not 0 <= metric_value <= 1):
            raise ValueError(
                f"baseline metric {metric_name} must be a number between 0 and 1"
            )
    return metrics


def run_offline_research_benchmark(
    cases: list[dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
    regression_threshold: float = 0.05,
    quality_config: dict[str, Any] | None = None,
    fixture_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a bounded, deterministic collection of synthetic research cases."""
    if not isinstance(cases, list) or not cases or len(cases) > MAX_CASES:
        raise ValueError(f"cases must contain 1 to {MAX_CASES} entries")
    if baseline is not None and not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")
    baseline_metrics = _validate_baseline_metrics(baseline)
    normalized_fixture_metadata = _validate_fixture_metadata(fixture_metadata)
    if quality_config is None:
        normalized_config = {"uncertainty_markers": list(DEFAULT_QUALITY_CONFIG["uncertainty_markers"])}
    elif not isinstance(quality_config, dict) or set(quality_config) != {"uncertainty_markers"}:
        raise ValueError("quality_config supports only the uncertainty_markers setting")
    else:
        markers = quality_config.get("uncertainty_markers")
        if (not isinstance(markers, list) or not markers or len(markers) > MAX_CONFIG_MARKERS
                or any(not isinstance(marker, str) or not marker.strip() or len(marker) > 80
                       for marker in markers)):
            raise ValueError("quality_config.uncertainty_markers must contain 1 to 20 non-empty strings up to 80 characters")
        normalized_config = {"uncertainty_markers": list(dict.fromkeys(marker.strip().lower() for marker in markers))}
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

    # Fixture overlap audit: compare normalized draft text and claim/source IDs.
    # This is a transparent lexical signal, not semantic similarity or proof of leakage.
    def _tokens(value: Any) -> set[str]:
        if not isinstance(value, str):
            return set()
        return {token for token in value.lower().split() if token.strip(".,!?;:\"'()[]{}")}

    case_signatures = []
    for case in normalized_cases:
        claim_items = case.get("claims") if isinstance(case.get("claims"), list) else []
        source_items = case.get("source_registry") if isinstance(case.get("source_registry"), list) else []
        claim_text = " ".join(
            str(item.get("text", "")) for item in claim_items if isinstance(item, dict)
        )
        refs = sorted({
            str(ref) for item in claim_items if isinstance(item, dict)
            for ref in (item.get("source_refs") if isinstance(item.get("source_refs"), list) else [])
        })
        source_ids = sorted({
            str(item.get("source_id")) for item in source_items
            if isinstance(item, dict) and item.get("source_id") is not None
        })
        draft_tokens = _tokens(case.get("draft"))
        claim_tokens = _tokens(claim_text)
        all_tokens = draft_tokens | claim_tokens
        case_signatures.append({
            "case_id": case["case_id"],
            "draft_tokens": draft_tokens,
            "claim_tokens": claim_tokens,
            "all_tokens": all_tokens,
            "source_refs": set(refs),
            "source_ids": set(source_ids),
        })
    overlap_pairs = []
    for index, left in enumerate(case_signatures):
        for right in case_signatures[index + 1:]:
            union = left["all_tokens"] | right["all_tokens"]
            token_jaccard = (
                round(len(left["all_tokens"] & right["all_tokens"]) / len(union), 4)
                if union else 1.0
            )
            shared_refs = sorted(left["source_refs"] & right["source_refs"])
            shared_source_ids = sorted(left["source_ids"] & right["source_ids"])
            if token_jaccard >= 0.5 or shared_refs or shared_source_ids:
                overlap_pairs.append({
                    "case_ids": [left["case_id"], right["case_id"]],
                    "token_jaccard": token_jaccard,
                    "shared_source_refs": shared_refs,
                    "shared_source_ids": shared_source_ids,
                    "flags": [
                        flag for flag, condition in (
                            ("high_lexical_overlap", token_jaccard >= 0.5),
                            ("shared_source_refs", bool(shared_refs)),
                            ("shared_source_registry_ids", bool(shared_source_ids)),
                        ) if condition
                    ],
                })
    # Exact duplicate audit excludes case_id so duplicate content with
    # different labels is not treated as independent evidence.
    canonical_case_payloads = [
        json.dumps(
            {key: case.get(key) for key in ("draft", "claims", "source_registry")},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        for case in normalized_cases
    ]
    unique_case_payloads = set(canonical_case_payloads)
    exact_duplicate_case_count = len(canonical_case_payloads) - len(unique_case_payloads)
    fixture_diversity = {
        "status": "exact_duplicates_found" if exact_duplicate_case_count else "no_exact_duplicates_found",
        "case_count": len(canonical_case_payloads),
        "unique_case_payload_count": len(unique_case_payloads),
        "exact_duplicate_case_count": exact_duplicate_case_count,
        "method": "exact canonical JSON equality of draft, claims, and source_registry; case_id excluded",
        "limitations": "Exact-content audit only; it does not establish semantic diversity or independent evidence.",
    }

    fixture_overlap = {
        "pair_count_flagged": len(overlap_pairs),
        "flagged_pairs": overlap_pairs,
        "threshold": 0.5,
        "method": "case-insensitive whitespace token Jaccard over draft plus claim text; exact source ID overlap",
        "limitations": "Lexical heuristic only. It can miss paraphrases, flag common boilerplate, and does not establish semantic duplication, leakage, independence, or quality.",
    }

    canonical = json.dumps(
        {"cases": normalized_cases, "baseline": baseline,
         "regression_threshold": regression_threshold, "quality_config": normalized_config},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    benchmark_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    results = []
    for case in normalized_cases:
        evaluation = evaluate_research_draft(
            draft=case["draft"],
            claims=case["claims"],
            source_registry=case["source_registry"],
            uncertainty_markers=tuple(normalized_config["uncertainty_markers"]),
        )
        results.append({
            "case_id": case["case_id"],
            "evaluation": evaluation,
        })

    metric_keys = BASELINE_METRICS
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
            "unevaluated_case_count": len(results) - len(values),
        }

    uncertainty_values = [result["evaluation"]["metrics"]["uncertainty_marker_coverage"] for result in results]
    aggregate["uncertainty_marker_coverage"] = {
        "mean": round(sum(uncertainty_values) / len(uncertainty_values), 4) if uncertainty_values else None,
        "evaluated_case_count": len(uncertainty_values),
        "unevaluated_case_count": len(results) - len(uncertainty_values),
    }

    baseline_comparison = None
    regression_summary = None
    if baseline is not None:
        baseline_comparison = {}
        regressions = []
        skipped_comparisons = []
        for key in metric_keys:
            current = aggregate[key]["mean"]
            previous = baseline_metrics.get(key)
            if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                delta = round(current - previous, 4)
                baseline_comparison[key] = {
                    "current_mean": current,
                    "baseline_mean": previous,
                    "delta": delta,
                    "status": "compared",
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
                reason = (
                    "current_metric_unavailable"
                    if not isinstance(current, (int, float))
                    else "baseline_metric_missing"
                )
                baseline_comparison[key] = {
                    "current_mean": current,
                    "baseline_mean": previous,
                    "delta": None,
                    "status": "skipped",
                    "reason": reason,
                }
                skipped_comparisons.append({"metric": key, "reason": reason})
        regression_status = (
            "regression_detected" if regressions
            else ("comparison_incomplete" if skipped_comparisons
                  else "no_regression_detected")
        )
        regression_summary = {
            "status": regression_status,
            "threshold": regression_threshold,
            "items": regressions,
            "skipped_comparison_count": len(skipped_comparisons),
            "skipped_comparisons": skipped_comparisons,
            "note": "Flags structural traceability metric drops only; not factual or trading performance. Skipped metrics are not evidence of a pass.",
        }

    return {
        "benchmark_id": benchmark_id,
        "benchmark_type": "offline_research_traceability",
        "research_only": True,
        "automatic_promotion": False,
        "model_training": False,
        "broker_execution": False,
        "deployment": False,
        "evaluator_version": BENCHMARK_EVALUATOR_VERSION,
        "fixture_origin": "caller_supplied",
        "fixture_metadata": normalized_fixture_metadata,
        "provenance_note": "Fixture provenance is caller-declared and not independently verified. Metadata is excluded from benchmark_id; the ID fingerprints benchmark inputs/configuration, not provenance claims.",
        "quality_config": normalized_config,
        "case_count": len(results),
        "fixture_overlap": fixture_overlap,
        "fixture_diversity": fixture_diversity,
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
