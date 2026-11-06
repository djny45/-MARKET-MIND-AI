# Offline Research Benchmark Records

The backend can export a deterministic JSON record for an offline research
traceability benchmark:

```python
from app.research_benchmark import run_offline_research_benchmark
from app.research_benchmark_record import serialize_benchmark_record

result = run_offline_research_benchmark(cases)
record_json = serialize_benchmark_record(result)
```

## Record contract

- `record_schema_version` identifies the export envelope schema (currently 1).
- `record_id` is a SHA-256 digest of the canonical benchmark result payload.
- `benchmark_id` identifies the benchmark input/configuration fingerprint.
- `result` retains the complete benchmark output, including per-case evaluations,
  aggregate metrics, baseline comparison, regression summary, and limitations.
- Serialization is canonical JSON (sorted keys, compact separators, UTF-8) and
  excludes wall-clock timestamps. Identical results therefore produce identical
  record bytes and IDs.

## SQLite history store

```python
from app.research_benchmark_store import BenchmarkRecordStore

store = BenchmarkRecordStore("data/research_benchmark_history.sqlite")
record_id = store.save(result)
record = store.get(record_id)
recent_records = store.list_records(limit=50)
```

The store is synchronous and local to the configured SQLite file. Back up the
SQLite file to retain the archive.

## Human-reviewed configuration proposals

Candidate configuration changes can be recorded for explicit review and linked
to an existing benchmark record:

```python
from app.research_promotion_review import PromotionReviewStore

reviews = PromotionReviewStore("data/research_benchmark_history.sqlite")
reviews.submit_review(
    proposal_id="proposal-001",
    benchmark_record_id=record_id,
    candidate_config={"example_parameter": 0.2},
    decision="rejected",  # or "approved"
    reviewer="human-reviewer",
    rationale="Document the evidence and reason for the decision.",
)
review = reviews.get_review("proposal-001")
```

Review records are append-only by proposal ID: duplicate IDs are rejected.
The foreign key requires the referenced benchmark record to exist. Approval is
only a stored review decision—it does **not** apply configuration, retrain a
model, deploy a change, or authorize trading. A real promotion pipeline still
needs candidate validation, independent regression gates, authorization, and
rollback controls.

The benchmark uses supplied fixtures and structural source-reference
traceability. It does **not** establish factual correctness, source entailment,
forecast quality, or profitability. Skipped baseline comparisons remain
incomplete, not passing.
