# Agent Task API Quickstart

For downstream agents integrating the MARKET-MIND-AI workspace. This documents existing FastAPI routes; inspect `backend/app/main.py` and request models before implementing clients.

## Recommended integration sequence

1. Discover worker IDs: `GET /api/workers?limit=550` or inspect `GET /api/worker-registry`.
2. Read the runtime boundary: `GET /api/analytical-agents/runtime`.
3. Load a relevant allowlisted playbook: `GET /api/skills`, then `GET /api/skills/{skill_id}`.
4. Submit a bounded research brief to one worker: `POST /api/analytical-agents/{worker_id}/tasks/queue`.
5. Track it with `GET /api/analytical-agent-tasks/{task_id}`.
6. Inspect task evidence: `GET /api/analytical-agent-tasks/{task_id}/audit`.
7. If present, retrieve quality metadata: `GET /api/analytical-agent-tasks/{task_id}/quality-evaluation`.

## Example queue request

```http
POST /api/analytical-agents/{worker_id}/tasks/queue
Content-Type: application/json

{
  "brief": "Summarize the supplied historical dataset and identify limitations.",
  "data": {
    "symbol": "SAMPLE",
    "interval": "1d",
    "source": "user_supplied",
    "status": "historical",
    "bars": []
  }
}
```

The example is illustrative only; use the exact Pydantic request model and data schema in the current code. Do not send credentials or sensitive account data.

## Status and timing behavior

- Queue endpoint returns HTTP `202` and a task ID with status `queued`.
- FastAPI `BackgroundTasks` executes the task in the current API process. This is not a durable distributed queue; a process restart can interrupt work.
- Poll task detail until a terminal status (`completed` or `failed`) or present the current status honestly. Do not mark `queued`/`running` as success.
- Recovery endpoint `POST /api/analytical-agent-tasks/recover` only requeues stale running tasks; it does not dispatch them.
- Supervisor dispatch is explicit: `POST /api/analytical-agent-supervisor/dispatch`. Review its request model and limits before calling.
- A task uses the shared configured intelligence provider and the worker's role context. It does not represent a separate model per worker.
- Research synthesis is bounded to the supplied brief/data. The task service does not fetch live market data.

## Alternate endpoints

- `POST /api/analytical-agents/{worker_id}/tasks`: bounded synchronous task submission.
- `POST /api/research/specialist-routing`: get deterministic keyword-based routing recommendations without queueing.
- `POST /api/research/route-and-queue`: route to matched specialists and queue tasks; background execution remains process-local.
- `GET /api/analytical-agents/{worker_id}/tasks`: list a worker's tasks.

## UI behavior

Show task ID, worker ID, current status, created/updated timestamps, and clear errors. Render result provenance and quality evaluation separately from synthesis. Preserve partial/unavailable states; do not fabricate market facts or sources.

## Guardrails

Research and historical analysis only. No broker credentials, live order placement, routing, modification, or cancellation. Do not turn research outputs into automated trading actions. Synthetic data must remain explicitly labeled synthetic.

## Validation checklist

- Test queued/running/completed/failed display states.
- Handle 422 request-model validation errors; 400 service validation errors (including unknown worker IDs on task submit/queue); and 404 unknown task/skill IDs or worker IDs on endpoints that explicitly return 404.
- Handle API unavailable/timeouts without claiming the task completed.
- Keep existing task/audit IDs and source metadata intact.
- Run backend tests and frontend build; report actual outcomes and commit SHA.
