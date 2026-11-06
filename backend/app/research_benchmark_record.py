"""Deterministic, versioned JSON records for offline research benchmark results.

Records are intended for archival and later comparison. They do not imply that
benchmark metrics establish factual correctness, trading performance, or learning.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

RECORD_SCHEMA_VERSION = 1


def serialize_benchmark_record(result: dict[str, Any]) -> str:
    """Return a stable JSON record with a content-derived record ID.

    No wall-clock timestamp is added: identical benchmark results produce
    byte-identical records, which makes offline artifacts reproducible.
    """
    if not isinstance(result, dict):
        raise ValueError("benchmark result must be an object")
    benchmark_id = result.get("benchmark_id")
    benchmark_type = result.get("benchmark_type")
    if not isinstance(benchmark_id, str) or not benchmark_id.strip():
        raise ValueError("benchmark result must include a benchmark_id")
    if benchmark_type != "offline_research_traceability":
        raise ValueError("unsupported benchmark_type")
    if not isinstance(result.get("case_count"), int) or isinstance(result.get("case_count"), bool):
        raise ValueError("benchmark result must include an integer case_count")
    if not isinstance(result.get("aggregate_metrics"), dict):
        raise ValueError("benchmark result must include aggregate_metrics")

    try:
        canonical_result = json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("benchmark result must be JSON-serializable") from exc

    record_id = hashlib.sha256(canonical_result.encode("utf-8")).hexdigest()
    record = {
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "record_id": record_id,
        "benchmark_id": benchmark_id,
        "benchmark_type": benchmark_type,
        "result": result,
    }
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )
