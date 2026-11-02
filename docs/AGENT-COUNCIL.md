# Specialist AI Agent Council

MARKET-MIND-AI exposes a bounded specialist AI-agent council API for research on **user-supplied data**.

## Run a council

`POST /api/agent-council/run`

Example request:

```json
{
  "agent_ids": ["worker_001", "worker_021"],
  "brief": "Compare the supplied observations and identify evidence gaps.",
  "data": {
    "observations": [
      {"metric": "sample_a", "value": 12},
      {"metric": "sample_b", "value": 15}
    ]
  }
}
```

The council endpoint currently accepts 1–8 registered specialist AI agent/bot IDs. A separate batch endpoint, POST /api/agent-council/batch, accepts up to 550 unique registered IDs and records each result through the existing task store. Batch execution uses bounded concurrency (default 4, configurable from 1 to 16) through the shared inference provider (not parallel independent model processes). Each member receives its own role/brain context and memory namespace, but all members use the same configured central inference provider. The endpoint does not fetch live market data.

## Review council output

`POST /api/agent-council/review`

Pass the returned council object as `council_result`. The review computes exact normalized-text fingerprints, reports missing analysis, and groups identical summaries. It does **not** infer semantic agreement, disagreement, or consensus.

## Current limits

- The registry represents 550 specialist AI agents/bots with distinct identities, role instructions, context, and memory namespaces. They may share one underlying inference engine; the count refers to agents, not separately hosted foundation models.
- The council is limited to eight members per request.
- The shared inference provider may be disabled or unavailable; in that case, member analysis is not produced.
- Cross-agent semantic synthesis, robust evidence adjudication, and disagreement scoring are not implemented yet.
- Research only: no paper trading, brokerage credentials, order routing, or automated execution.


## Registry-wide batch research

POST /api/agent-council/batch

Example request:

```json
{
  "agent_ids": ["worker_001", "worker_021"],
  "brief": "Analyze these supplied research observations",
  "data": {"observations": ["sample values"]}
}
```

The batch API supports up to 550 unique registered agent IDs. Each selected agent is submitted through the existing analytical task lifecycle and returns its task ID, status, execution mode, and result/error. Execution is bounded and concurrent using the shared inference provider; the default concurrency is 4 and the API accepts max_concurrency from 1 to 16. Per-agent errors are isolated and results preserve request order. This is not 550 independent model processes or a durable distributed queue. Configure the provider before expecting substantive analysis. With the provider disabled, task outcomes explicitly report the unavailable/not-configured state.


## Terminology

Use **AI agents**, **specialist agents**, or **analytical bots** for the 550 registered identities. Avoid calling them models or workers in user-facing product copy. Internal legacy identifiers such as `worker_001` are retained for backward-compatible APIs and database records; they are IDs, not the product's conceptual architecture. A shared inference engine is infrastructure used by agents, not the agent itself.
