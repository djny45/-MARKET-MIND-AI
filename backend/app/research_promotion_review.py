"""Reviewed promotion gate for benchmark-backed agent configuration proposals.

This module records review decisions only. It does not modify active agent
configuration or deploy changes.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

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


def promotion_eligibility(benchmark_record: dict[str, Any]) -> dict[str, Any]:
    """Return explicit gate status; missing or incomplete comparisons never pass."""
    if not isinstance(benchmark_record, dict):
        raise ValueError("benchmark_record must be an object")
    result = benchmark_record.get("result")
    if not isinstance(result, dict):
        raise ValueError("benchmark_record must include a result object")
    summary = result.get("regression_summary")
    comparisons = result.get("baseline_comparison")
    if not isinstance(summary, dict) or not isinstance(comparisons, dict):
        return {"eligible": False, "status": "baseline_required",
                "reasons": ["baseline comparison is missing"]}
    reasons = []
    if summary.get("status") != "no_regression_detected":
        reasons.append("benchmark regression status is not clean")
    if summary.get("skipped_comparison_count") != 0:
        reasons.append("benchmark contains skipped comparisons")
    if not comparisons:
        reasons.append("benchmark comparison metrics are missing")
    for metric, comparison in comparisons.items():
        if not isinstance(comparison, dict) or comparison.get("status") != "compared":
            reasons.append(f"metric {metric} was not compared")
        elif not isinstance(comparison.get("delta"), (int, float)) or isinstance(
                comparison.get("delta"), bool):
            reasons.append(f"metric {metric} has no numeric delta")
    return {"eligible": not reasons,
            "status": "eligible" if not reasons else "blocked",
            "reasons": reasons}


class PromotionReviewStore:
    """Persist explicit human review decisions for candidate configurations."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        # Ensure the parent benchmark table exists before SQLite creates its FK.
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
        self,
        *,
        proposal_id: str,
        benchmark_record_id: str,
        candidate_config: dict[str, Any],
        decision: str,
        reviewer: str,
        rationale: str,
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
