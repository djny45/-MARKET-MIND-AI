# AI Agent Integration Map

A compact map for the user's coding agents integrating the terminal and remaining feature modules. This is based on the current repository interfaces; verify signatures and tests before depending on them.

## Backend discovery endpoints

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /api/system/capabilities` | Platform capability summary | Use as broad capability discovery; inspect `pipeline.system_capabilities()` before relying on individual fields. |
| `GET /api/analytical-agents/runtime` | Agent runtime topology and limitations | Describes worker contexts/shared inference; not 550 independent model instances. |
| `GET /api/analytical-agents/{worker_id}/brain` | Worker-specific role/context | Unknown worker IDs return 404. |
| `GET /api/worker-registry` | Registry manifest and integrity evaluation | Use for registered worker IDs instead of inventing IDs. |
| `GET /api/workers?department=&limit=` | Worker listing | Limit is bounded to 550. |
| `GET /api/skills` | Allowlisted skill metadata | Skill list is advisory; it does not grant permissions or install tools. |
| `GET /api/skills/{skill_id}` | Load one allowlisted skill | Unknown or excluded skills return 404. |
| `GET /api/worker-runtime` | Runtime/routing status | Do not infer durable or autonomous behavior from this status. |

## Research-task integration

Existing task routes and service functions are defined in `backend/app/main.py` and `backend/app/analytical_agent_tasks.py`. Inspect the exact route signatures and response bodies before implementing a client. Tasks use persisted SQLite records, but execution is currently dispatched through process-local FastAPI background tasks; this is not a distributed durable queue.

For task results, preserve the task ID, worker ID, task status, timestamps, source context, warnings, and quality-evaluation status. A task being queued or running is not a completed result.

## Existing frontend integration points

Inspect these components before adding terminal panels or duplicate controls:

- `frontend/src/App.tsx` — existing main workspace and API orchestration.
- `frontend/src/PriceChart.tsx` — existing historical chart and provenance display.
- `frontend/src/AgentNetwork.tsx` — agent network view.
- `frontend/src/AgentPositionMonitor.tsx` — existing agent monitoring UI; do not infer broker positions from research output.
- `frontend/src/OpenBBTerminal.tsx` — existing OpenBB-related UI component. The user owns terminal redesign through their AI agents; extend only when explicitly assigned.

## Market data and research contracts

Use `backend/app/market_data.py` and `backend/app/market_data_validation.py` for the normalized OHLCV batch and validation rules. Existing data batches carry source, status, retrieval time, interval, symbol, and warnings. Keep these fields attached to chart, indicator, and agent outputs.

Distinguish:

- historical provider data;
- delayed/unofficial provider data;
- synthetic fixture data;
- user-imported/manual data;
- unknown provenance.

Do not relabel synthetic fixtures as real market data. Do not silently fill missing values or conceal provider limitations.

## Integration ownership

- The user's AI agents build the terminal and assigned feature modules.
- Core work should focus on shared backend contracts, validation, provenance, and integration tests.
- Avoid rebuilding the chart, worker registry, skill catalog, agent network, or existing workflow editor.
- Keep research-only functionality: no brokerage credential capture, live order placement, order routing, modification, or cancellation.


## Access-control boundary

The current research-task, dispatch, recovery, and review routes are not protected by authentication or per-user authorization. Treat them as trusted-local development interfaces only; do not expose them to the public internet. Before any public deployment, add authentication, authorization, rate limits, and independent security review. The existing SQLite persistence does not imply user isolation.

## Smoke-test checklist for an integrating agent

1. Backend starts and OpenAPI loads.
2. Capability, worker, runtime, and skill discovery endpoints return valid responses.
3. Unknown worker and skill IDs produce expected 404 responses.
4. Agent task UI handles queued/running/completed/failed states without claiming a result prematurely.
5. Chart and terminal show the data source and historical/synthetic/manual status.
6. Existing frontend build and backend tests pass, or failures are explicitly recorded.
