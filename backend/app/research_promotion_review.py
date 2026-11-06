"""Reviewed promotion gate for benchmark-backed agent configuration proposals.

This module records review decisions only. It does not modify active agent
configuration or deploy changes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.research_benchmark import BASELINE_METRICS
from app.research_benchmark_record import RECORD_SCHEMA_VERSION
from app.research_benchmark_store import BenchmarkRecordStore


_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_promotion_reviews (
    proposal_id TEXT PRIMARY KEY,
    benchmark_record_id TEXT NOT NULL,
    candidate_config_json TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reviewer TEXT NOT NULL,
    rationale TEXT NOT NULL,
    FOREIGN KEY (benchmark_record_id)
        REFERENCES research_benchmark_records(record_id)
);
"""


def _record_integrity_reasons(benchmark_record: dict[str, Any]) -> list[str]:
    """Check envelope fields and content hash before trusting archived metrics."""
    reasons: list[str] = []
    result = benchmark_record.get("result")
    record_id = benchmark_record.get("record_id")
    if benchmark_record.get("record_schema_version") != RECORD_SCHEMA_VERSION:
        reasons.append("benchmark record schema version is unsupported")
    if not isinstance(record_id, str) or not record_id:
        reasons.append("benchmark record ID is missing")
    if not isinstance(result, dict):
        reasons.append("benchmark record result is missing")
        return reasons
    if benchmark_record.get("benchmark_id") != result.get("benchmark_id"):
        reasons.append("benchmark ID does not match record result")
    if benchmark_record.get("benchmark_type") != result.get("benchmark_type"):
        reasons.append("benchmark type does not match record result")
    try:
        canonical_result = json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        reasons.append("benchmark result is not canonical JSON")
        return reasons
    expected_id = hashlib.sha256(canonical_result.encode("utf-8")).hexdigest()
    if record_id != expected_id:
        reasons.append("benchmark record content hash is invalid")
    return reasons


def promotion_eligibility(benchmark_record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on tampered records and missing, inconsistent, or regressing metrics."""
    if not isinstance(benchmark_record, dict):
        raise ValueError("benchmark_record must be an object")
    result = benchmark_record.get("result")
    if not isinstance(result, dict):
        raise ValueError("benchmark_record must include a result object")

    reasons = _record_integrity_reasons(benchmark_record)
    summary = result.get("regression_summary")
    comparisons = result.get("baseline_comparison")
    if not isinstance(summary, dict) or not isinstance(comparisons, dict):
        reasons.append("baseline comparison is missing")
        return {"eligible": False, "status": "baseline_required",
                "reasons": reasons}

    if summary.get("status") != "no_regression_detected":
        reasons.append("benchmark regression status is not clean")
    if summary.get("skipped_comparison_count") != 0:
        reasons.append("benchmark contains skipped comparisons")
    if set(comparisons) != set(BASELINE_METRICS):
        reasons.append("benchmark comparison metric set is incomplete or unsupported")

    threshold = summary.get("threshold")
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not 0 <= threshold <= 1):
        reasons.append("regression threshold is invalid")
        threshold = None

    expected_regressions = []
    expected_skipped = 0
    for metric in BASELINE_METRICS:
        comparison = comparisons.get(metric)
        if not isinstance(comparison, dict) or comparison.get("status") != "compared":
            reasons.append(f"metric {metric} was not compared")
            expected_skipped += 1
            continue
        current = comparison.get("current_mean")
        baseline = comparison.get("baseline_mean")
        delta = comparison.get("delta")
        numeric = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
        if not all(numeric(value) for value in (current, baseline, delta)):
            reasons.append(f"metric {metric} has non-numeric comparison values")
            continue
        if round(current - baseline, 4) != delta:
            reasons.append(f"metric {metric} delta is inconsistent")
        if not 0 <= current <= 1 or not 0 <= baseline <= 1:
            reasons.append(f"metric {metric} is outside the expected 0–1 range")
        if threshold is not None and delta < 0 and delta <= -threshold:
            reasons.append(f"metric {metric} violates the regression threshold")
            expected_regressions.append({
                "metric": metric,
                "delta": delta,
                "threshold": threshold,
                "severity": "regression",
            })

    if summary.get("skipped_comparison_count") != expected_skipped:
        reasons.append("benchmark skipped-comparison count is inconsistent")
    if summary.get("items") != expected_regressions:
        reasons.append("benchmark regression items are inconsistent with metric deltas")
    expected_status = (
        "regression_detected" if expected_regressions
        else ("comparison_incomplete" if expected_skipped
              else "no_regression_detected")
    )
    if summary.get("status") != expected_status:
        reasons.append("benchmark regression status is inconsistent with comparisons")

    return {"eligible": not reasons,
            "status": "eligible" if not reasons else "blocked",
            "reasons": reasons}


class PromotionReviewStore:
    """Persist explicit human review decisions for candidate configurations."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        BenchmarkRecordStore(self.database_path)
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def submit_review(
        self, *, proposal_id: str, benchmark_record_id: str,
        candidate_config: dict[str, Any], decision: str,
        reviewer: str, rationale: str,
    ) -> None:
        """Store a review; approval requires complete, regression-free comparisons."""
        required = {
            "proposal_id": proposal_id,
            "benchmark_record_id": benchmark_record_id,
            "reviewer": reviewer,
            "rationale": rationale,
        }
        for name, value in required.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        if not isinstance(candidate_config, dict):
            raise ValueError("candidate_config must be an object")
        try:
            config_json = json.dumps(
                candidate_config, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate_config must be JSON-serializable") from exc

        if decision == "approved":
            benchmark = BenchmarkRecordStore(self.database_path).get(benchmark_record_id)
            if benchmark is None:
                raise ValueError("benchmark record does not exist")
            gate = promotion_eligibility(benchmark)
            if not gate["eligible"]:
                raise ValueError("promotion approval blocked: " + "; ".join(gate["reasons"]))

        with self._connect() as connection:
            connection.execute(
                """INSERT INTO research_promotion_reviews
                   (proposal_id, benchmark_record_id, candidate_config_json,
                    decision, reviewer, rationale)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (proposal_id, benchmark_record_id, config_json, decision,
                 reviewer.strip(), rationale.strip()),
            )

    def get_review(self, proposal_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT proposal_id, benchmark_record_id, candidate_config_json,
                          decision, reviewer, rationale
                   FROM research_promotion_reviews WHERE proposal_id = ?""",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        review = dict(row)
        review["candidate_config"] = json.loads(review.pop("candidate_config_json"))
        return review

    def list_reviews(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer between 1 and 500")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT proposal_id, benchmark_record_id, decision, reviewer, rationale
                   FROM research_promotion_reviews ORDER BY rowid DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
