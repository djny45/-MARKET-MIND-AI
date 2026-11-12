# Worker Registry Integrity

The worker registry is a deterministic manifest of **550 analytical worker templates**. It is not a fleet of 550 independently running models. All profiles reference the shared `shared_central_intelligence` core, and registry evaluation does not execute inference or broker actions.

## Validation layers

`evaluate_registry()` checks three separate layers:

1. **Worker profiles** — expected count and ordered IDs, required non-empty fields, allowed department, worker kind, template status, and shared-core identity.
2. **Worker skill references** — every `skill_refs` value must be a string, resolve to an allowlisted catalog ID, be available on disk, and occur only once per worker.
3. **Skill catalog integrity** — the catalog must be a list; each entry must be an object with a non-empty string `id` and a boolean `available` field; IDs must be unique.

Catalog integrity is reported in `skill_catalog_integrity`:

| Field | Meaning |
| --- | --- |
| `catalog_entry_count` | Number of catalog entries received |
| `valid_entry_count` | Entries that satisfy the required shape |
| `malformed_entry_indexes` | Zero-based indexes of entries with an invalid shape |
| `duplicate_skill_ids` | Repeated IDs found in the catalog |

A non-list catalog is normalized to an empty list for safe reporting and adds `skill_catalog_not_a_list` to the errors. Invalid entries and duplicate IDs also make the registry invalid; they are not silently accepted.

## Skill coverage is not semantic alignment

The department/domain matrix reports which catalog domains are represented by assigned research skill IDs. It is explicitly labeled `catalog_domain_coverage_only_not_semantic_alignment`. It does not prove that a skill is appropriate for a worker's department or specialty.

The `specialty_skill_alignment` result remains `not_evaluated` until a curated mapping has documented rationale and review evidence. Do not infer semantic fit from a valid ID, a file being present, or a non-zero coverage count.

## Safety and execution boundary

Worker profiles are templates and skill references are guidance links. The registry is not an execution engine. The current boundary remains:

- no independent model per worker;
- no autonomous model updates or self-promotion;
- no broker or order execution;
- no claim of live market coverage from catalog validation.

## Tests

Run the backend unit suite from the repository root:

```bash
python -m unittest discover -s backend/tests -v
```

The worker registry tests cover valid manifests, malformed profiles, invalid and duplicate worker skill references, unavailable skills, malformed catalog entries, duplicate catalog IDs, and explicit non-alignment claims.


## Runtime context isolation

Research-task execution binds a task-local agent scope using Python `ContextVar`. The scope carries the registered worker ID, task ID, worker memory namespace, and shared intelligence-core ID. Concurrent asyncio tasks receive independent context values, and nested scopes restore their parent value when closed. The executor resets its scope in a `finally` block on both successful and failed synthesis paths.

This is in-process context isolation, not a distributed context-propagation system. Any future integration that crosses raw thread or process boundaries must explicitly propagate or re-establish the scope. The current implementation does not add NeMo Relay instrumentation or a new inference provider.

Workflow resume checkpoints are validated before execution: completed node IDs must be unique and belong to the current DAG, and each completed node must have a matching completed task record and result. Result and task maps cannot reference unknown nodes. This prevents malformed or stale checkpoint state from silently skipping work. Checkpoints remain caller-supplied state; this validation does not provide durable storage or cryptographic authenticity.

## Analytical output contract enforcement

Workflow output validation checks both the declared top-level shape and the value types of analytical fields. Series outputs (including MACD and Bollinger components) must be lists of finite numeric values; the RSI `series` may additionally contain leading `null` entries for its calculation warm-up, but nulls after the first numeric value are rejected. Period metadata and indicator period parameters must be positive integers; booleans, numeric strings, fractional values, zero, and negative values are rejected rather than silently coerced. Descriptive metadata may remain textual, but it cannot replace a numeric analytical series. This is structural validation only and does not establish that source data is authentic or that a calculation is economically meaningful.


Checkpoint validation also verifies each completed task's recorded node type against the current DAG and re-runs that node type's output contract against its saved result before allowing resume. This prevents a structurally valid but malformed result, or a result recorded under the wrong worker type, from bypassing validation when downstream nodes consume it.

Queued agent task lifecycle hardening keeps persisted-input decoding inside the guarded execution block. A malformed stored input is finalized as a failed task rather than remaining in the running state. Task inspection returns a bounded `invalid_persisted_json` marker when stored input or result JSON cannot be decoded, so a corrupt record remains inspectable. Agent-scope cleanup errors are caught during finalization; an otherwise successful task is downgraded to failed rather than being left without a terminal status. These safeguards complement atomic task claiming, execution-token fencing, bounded stale recovery, and audit events.