# Cloud Model Tier Routing

## Policy

MARKET-MIND-AI assigns model tiers to its 550 logical research-agent profiles:

- `worker_001` through `worker_020`: premium tier (20 division leads).
- `worker_021` through `worker_550`: standard tier (530 specialist profiles).

Both tiers use the configured cloud provider. Local inference providers are not accepted by
`backend/app/model_access.py`.

## Configuration

Set these values in the deployment secret/environment manager, never in source control:

- `MARKET_MIND_MODEL_PROVIDER=mercury`
- `MARKET_MIND_PREMIUM_MODEL=<provider-supported-premium-model-id>`
- `MARKET_MIND_BASIC_MODEL=<provider-supported-standard-model-id>`
- `INCEPTION_API_KEY=<secret>`
- `INTELLIGENCE_CORE_ENABLED=true`

Model IDs must be verified against the provider account and current provider model catalogue.
This repository does not assume that a particular basic/premium model ID is available.

## Current implementation boundary

The tier resolver and agent brain metadata are implemented and tested. They report whether
configuration values are present without returning secrets. This slice does **not** claim
that 550 agents are running, that cloud API credentials are installed, or that tier-specific
inference has passed an end-to-end provider health check. The shared inference request path
must pass the agent ID into the gateway before model assignments become active at runtime.

No local model server, broker execution, order placement, or autonomous financial execution
is part of this design. Research tasks remain educational and evidence-grounded.
