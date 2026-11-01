# Workflow checkpoint recovery

Workflow runs are persisted before DAG execution begins. After each completed DAG
layer, the engine stores a SQLite checkpoint containing completed node IDs, their
results, task records, and the completed-layer count.

## Recovery guarantees

- Resume uses the original serialized request stored with the parent run.
- A SHA-256 fingerprint of the canonical request JSON is stored with each checkpoint.
- Recovery rejects a checkpoint whose fingerprint is missing or does not match the
  original request, and rejects checkpoint node IDs absent from the saved graph.
- Completed nodes are restored and skipped; incomplete nodes are scheduled again.
- Each resumed run is a new run with the original run ID recorded as its parent.
- Legacy checkpoints without a fingerprint are intentionally not resumed; start a
  fresh research run instead.

## Boundaries

Checkpoints are layer-granular, not per-instruction snapshots. A process interruption
inside a layer can cause that layer's unfinished nodes to run again. Checkpoint data
is local SQLite state and inherits the deployment's backup and disk durability
properties. This feature is for deterministic research and paper-only workflows;
it does not enable brokerage connectivity, order routing, or live trading.

## Recovery observability

The resume response reports the source run ID, number of restored task outputs,
checkpoint age in seconds, checkpoint schema version, and completed layer count.
The Run History inspector surfaces the restored-task count and checkpoint age.
Each snapshot carries its own UTC timestamp so age is measured from the checkpoint,
not merely from the parent run's creation time.

Before restoration, the API verifies that every completed node has both a saved
result and a task record marked completed. Internally inconsistent checkpoints are
rejected with HTTP 409 rather than partially restored.
