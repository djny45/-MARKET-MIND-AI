# Cloud Model Tier Routing

## Policy

MARKET-MIND-AI assigns model tiers to its 550 logical research-agent profiles:

- `worker_001` through `worker_020`: premium tier (20 division leads).
- `worker_021` through `worker_550`: standard tier (530 specialist profiles).

Both tiers use the configured cloud provider. Local inference providers are not accepted by
`backend/app/model_access.py` for agent-scoped synthesis.

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

The tier resolver, agent brain metadata, and agent-ID-aware shared synthesis path are implemented.
Research-task execution and council synthesis pass each logical agent ID to the shared core;
agent-scoped requests resolve the corresponding tier and target the fixed Mercury HTTPS endpoint.
When the tier configuration is incomplete, or the provider request fails, synthesis returns a
non-success status and leaves the deterministic research report authoritative. It does not
fall back to Ollama or FreeLLMAPI for an agent-scoped request.

Configuration readiness only reports the presence of settings. This repository does **not**
establish that deployment credentials are installed, model IDs are supported by the provider,
provider health has been verified, or end-to-end cloud inference is operational. Those require
deployment-side configuration and a successful, controlled provider verification.

The non-agent-scoped compatibility path may still use the separately configured shared provider;
the cloud-only tier guarantee described above applies to calls that supply a registered
`agent_id`.

No broker execution, order placement, or autonomous financial execution is part of this design.
Research tasks remain educational and evidence-grounded.
