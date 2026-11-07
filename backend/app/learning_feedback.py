"""Deterministic comparisons between current research metrics and approved evidence.

Approval is an operator label, not proof of correctness. This module reports
comparisons for review; it never changes models, strategies, or memory records.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .worker_memory import list_learning_candidates


def evaluate_learning_feedback(
    worker_id: str,
    current_metrics: dict[str, Any],
    *,
    stale_after_days: int = 30,
    tolerance: float = 0.0001,
) -> dict[str, Any]:
    """Compare supplied metrics with recent approved candidates for one worker."""
    if not isinstance(current_metrics, dict) or not 1 <= len(current_metrics) <= 100:
        raise ValueError("current_metrics must be an object with 1 to 100 entries")
    if not isinstance(stale_after_days, int) or isinstance(stale_after_days, bool) or not 1 <= stale_after_days <= 3650:
        raise ValueError("stale_after_days must be between 1 and 3650")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise ValueError("tolerance must be a finite number between 0 and 1e12")
    try:
        tolerance = float(tolerance)
    except (OverflowError, ValueError):
        raise ValueError("tolerance must be a finite number between 0 and 1e12") from None
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1e12:
        raise ValueError("tolerance must be a finite number between 0 and 1e12")

    normalized = {}
    for name, value in current_metrics.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise ValueError("metric names must be non-empty strings of at most 64 characters")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"metric {name} must be a finite number")
        try:
            numeric_value = float(value)
        except (OverflowError, ValueError):
            raise ValueError(f"metric {name} must be a finite number") from None
        if not math.isfinite(numeric_value):
            raise ValueError(f"metric {name} must be a finite number")
        normalized[name] = numeric_value

    listing = list_learning_candidates(worker_id, limit=200)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_after_days)
    comparisons = []
    for candidate in listing["candidates"]:
        if candidate["review_status"] != "approved":
            continue
        metrics = candidate["content"].get("metrics")
        if not isinstance(metrics, dict):
            continue
        matched = []
        for name, current in normalized.items():
            previous = metrics.get(name)
            if isinstance(previous, bool) or not isinstance(previous, (int, float)):
                continue
            try:
                previous = float(previous)
            except (OverflowError, ValueError):
                continue
            if not math.isfinite(previous):
                continue
            delta = current - previous
            matched.append({
                "metric": name,
                "current": current,
                "approved_reference": previous,
                "delta": round(delta, 10),
                "status": "changed" if abs(delta) > tolerance else "within_tolerance",
            })
        if not matched:
            continue
        try:
            created_at = datetime.fromisoformat(candidate["created_at"].replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - created_at).days)
            is_stale = created_at < cutoff
        except (TypeError, ValueError, AttributeError):
            age_days = None
            is_stale = None
        changed_count = sum(item["status"] == "changed" for item in matched)
        comparisons.append({
            "candidate_memory_id": candidate["memory_id"],
            "candidate_created_at": candidate["created_at"],
            "candidate_age_days": age_days,
            "stale_reference": is_stale,
            "quality_status": candidate["quality_status"],
            "source_refs": candidate["source_refs"],
            "review": candidate["latest_review"],
            "comparison_count": len(matched),
            "changed_count": changed_count,
            "comparisons": matched,
            "status": "differences_detected" if changed_count else "within_tolerance",
        })

    comparisons.sort(
        key=lambda item: (
            item["stale_reference"] is True,
            item["candidate_created_at"],
        ),
        reverse=True,
    )
    changed_total = sum(item["changed_count"] for item in comparisons)
    if not comparisons:
        status = "no_comparable_approved_evidence"
    elif changed_total:
        status = "review_required_differences_detected"
    else:
        status = "no_material_metric_differences"
    return {
        "worker_id": worker_id,
        "status": status,
        "current_metrics": normalized,
        "approved_candidates_compared": len(comparisons),
        "changed_metric_comparisons": changed_total,
        "comparisons": comparisons,
        "scan_limit": 200,
        "stale_after_days": stale_after_days,
        "tolerance": float(tolerance),
        "note": (
            "Deterministic numeric comparison only. Differences and age flags are review cues, "
            "not evidence that current or approved values are correct. No source validation, "
            "model training, strategy change, or automatic promotion occurs."
        ),
    }
