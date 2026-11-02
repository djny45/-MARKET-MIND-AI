# Specialist AI Agent Council

MARKET-MIND-AI exposes a bounded specialist-council API for research on **user-supplied data**.

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

The council currently accepts 1–8 registered specialist agent IDs. Each member receives its own role/brain context and memory namespace, but all members use the same configured central inference provider. The endpoint does not fetch live market data.

## Review council output

`POST /api/agent-council/review`

Pass the returned council object as `council_result`. The review computes exact normalized-text fingerprints, reports missing analysis, and groups identical summaries. It does **not** infer semantic agreement, disagreement, or consensus.

## Current limits

- Agent profiles are not 550 separately hosted foundation models.
- The council is limited to eight members per request.
- The shared inference provider may be disabled or unavailable; in that case, member analysis is not produced.
- Cross-agent semantic synthesis, robust evidence adjudication, and disagreement scoring are not implemented yet.
- Research only: no paper trading, brokerage credentials, order routing, or automated execution.
