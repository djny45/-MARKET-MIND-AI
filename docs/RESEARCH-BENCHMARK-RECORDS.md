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

The optional local store archives records and uses `record_id` as its primary key:

```python
from app.research_benchmark_store import BenchmarkRecordStore

store = BenchmarkRecordStore("data/research_benchmark_history.sqlite")
record_id = store.save(result)  # idempotent for identical result records
record = store.get(record_id)
recent_records = store.list_records(limit=50)
```

The store is synchronous and local to the configured SQLite file. It does not
schedule benchmark runs, train a model, promote agent configurations, or execute
trades. Back up the SQLite file if you need to retain the archive.

The benchmark evaluates supplied fixtures and structural source-reference
traceability. It does **not** establish factual correctness, source entailment,
forecast quality, or profitability. A skipped baseline comparison remains
incomplete, not a passing result.
