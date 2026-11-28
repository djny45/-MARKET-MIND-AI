# n8n Workflow Evidence Review

## Scope
This review covers the tracked evidence file `docs/uat-evidence/workflow.json` on `feature/motion-ai-3d-terminal`. It is an API/task-dispatch evidence snapshot, **not an exported n8n workflow**. It does not contain an n8n `nodes` array, `connections` graph, node type versions, activation state, credential references, or runnable trigger definitions.

## Observed evidence
- Routing response: HTTP 200; 10 candidates; `worker_001` selected.
- Queue response: HTTP 202; task reported as `queued`.
- Task listing/detail/audit endpoints returned HTTP 200.
- Supervisor dispatch summary reports 1 selected and 1 dispatched task, with zero dispatch errors.
- Dispatch mode is `bounded_sqlite_queue_snapshot`; the evidence explicitly states this is a single-host SQLite queue, not a distributed broker.

## Interpretation
This file documents an application worker/task orchestration path. It does **not** establish that an n8n workflow was imported, activated, or executed. The CI job separately reported starting optional n8n and checking its health and private-network reachability; that is service smoke evidence, not proof that this specific JSON is an importable n8n workflow.

## Required next validation
1. Preserve this evidence as a snapshot; do not import it into n8n.
2. Obtain the actual n8n workflow export from the intended n8n instance.
3. Run the repository's structural workflow checker against that export.
4. Review expressions, Code nodes, credentials and all external writes.
5. Test valid, malformed and duplicate events in an isolated n8n instance with disposable data; test cross-run idempotency separately if any durable writes occur.

## Status
**Evidence classified; no n8n import or execution performed.** This review does not claim runtime validation of an n8n workflow.
