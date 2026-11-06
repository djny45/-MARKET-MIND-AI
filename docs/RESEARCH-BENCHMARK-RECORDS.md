# Offline Research Benchmark Records

The backend exports deterministic JSON records for offline research traceability
benchmarks. Records can be archived in SQLite and linked to reviewed candidate
configuration proposals.

## Benchmark record export

```python
from app.research_benchmark import run_offline_research_benchmark
from app.research_benchmark_record import serialize_benchmark_record

result = run_offline_research_benchmark(cases)
record_json = serialize_benchmark_record(result)
```

- `record_schema_version` identifies the envelope schema.
- `record_id` is a SHA-256 digest of the canonical result payload.
- `benchmark_id` identifies the benchmark input/configuration fingerprint.
- Serialization is canonical JSON without wall-clock timestamps.

## SQLite history

```python
from app.research_benchmark_store import BenchmarkRecordStore

store = BenchmarkRecordStore("data/research_benchmark_history.sqlite")
record_id = store.save(result)
record = store.get(record_id)
recent_records = store.list_records(limit=50)
```

The store is local and synchronous. Back up its SQLite file to retain history.

## Candidate review and approval gate

```python
from app.research_promotion_review import (
    PromotionReviewStore, promotion_eligibility,
)

benchmark_record = store.get(record_id)
gate = promotion_eligibility(benchmark_record)
```

Before evaluating metric eligibility, the promotion gate verifies the record
schema version, envelope/result benchmark identifiers and types, and the
SHA-256 content hash. Altered result payloads or inconsistent envelope fields
are blocked. This is integrity checking, not a cryptographic signature or
proof of who produced the record.

The gate also blocks approval if there is no baseline comparison, any metric
was skipped, the regression status is not `no_regression_detected`, the metric
set is incomplete, or comparison values/deltas are missing or inconsistent.
An explicit reviewer decision and rationale are then stored:

```python
reviews = PromotionReviewStore("data/research_benchmark_history.sqlite")
reviews.submit_review(
    proposal_id="proposal-001",
    benchmark_record_id=record_id,
    candidate_config={"example_parameter": 0.2},
    decision="approved",  # or "rejected"
    reviewer="human-reviewer",
    rationale="Record the evidence supporting this decision.",
)
```

Approval is only a stored review decision. It does not modify active agent
configuration, retrain a model, deploy code, or authorize trades. The gate is
not a substitute for independent benchmark quality, candidate-specific testing,
authorization, or rollback controls.

## Limitations

This benchmark uses supplied fixtures and measures structural source-reference
traceability only. It does not establish factual correctness, source entailment,
forecast quality, profitability, or autonomous learning. Skipped comparisons are
incomplete, never passing.
