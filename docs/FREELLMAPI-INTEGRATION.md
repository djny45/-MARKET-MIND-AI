# FreeLLMAPI integration

MARKET-MIND-AI contains an adapter in `backend/app/freellmapi_adapter.py` for the **single shared intelligence core**. It connects to a separately running FreeLLMAPI OpenAI-compatible gateway. It does not install or host FreeLLMAPI inside MARKET-MIND-AI or create one model per analytical worker.

## 1. Run FreeLLMAPI separately

FreeLLMAPI requires its own runtime (Docker or Node.js) and provider configuration. Follow its upstream documentation:

- Project: https://github.com/tashfeenahmed/freellmapi
- Install guide: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/install/01-install.md
- OpenAI-compatible API reference: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/api/01-rest-api.md

Start the gateway, configure provider credentials/models in its dashboard, and copy its unified API key. The documented local API base is `http://localhost:3001/v1`; use `127.0.0.1` when configuring this backend on the same host.

**The unified key is a secret.** Do not put it in GitHub source, commits, screenshots, public issues, or frontend code. Keep it in a local environment file or your deployment platform's secret store. FreeLLMAPI forwards requests to upstream providers configured by the user; their quotas, availability, privacy policies, and terms still apply.

## 2. Configure MARKET-MIND-AI

Set these variables for the backend process:

```dotenv
INTELLIGENCE_CORE_ENABLED=true
INTELLIGENCE_CORE_PROVIDER=freellmapi
FREELLMAPI_BASE_URL=http://127.0.0.1:3001/v1
FREELLMAPI_API_KEY=replace-with-your-local-unified-key
FREELLMAPI_MODEL=auto
```

The model value must be supported by the FreeLLMAPI gateway (for example, `auto` or a model identifier available in its dashboard). The adapter accepts a base URL with or without the `/v1` suffix, appends `/chat/completions` without duplicating `/v1`, sends a Bearer token, and requests a non-streaming OpenAI-compatible completion.

Restart the MARKET-MIND-AI backend after changing environment variables.

## 3. Network boundary

The current adapter intentionally allows **loopback hosts only**. Run both services on the same host for this integration.

If the backend and gateway are separate containers, `127.0.0.1` inside the backend container points to that container—not the gateway. A Docker service name such as `http://freellmapi:3001` is not accepted by the current loopback-only policy. Do not expose the gateway publicly or weaken this restriction just to make container networking work. A future trusted-network design would need explicit network controls and authentication review.

## 4. Verify configuration and a real completion

- `GET /api/intelligence-core` reports provider configuration without contacting the gateway. A configured status means **configured, not health-checked**.
- `POST /api/intelligence-core/synthesize` accepts a bounded, caller-supplied research JSON payload and attempts a real completion when the provider is configured.
- A successful request should return `provider: freellmapi_local` and `status: completed`. When FreeLLMAPI supplies its documented `X-Routed-Via` response header, MARKET-MIND-AI exposes it as `routed_via` (for example, the provider/model that served the request). This is routing telemetry, not a reliability or quality score. The documented `X-Fallback-Attempts` header is also exposed as `fallback_attempts` when it contains a numeric value. FreeLLMAPI percent-encodes non-ASCII characters in `X-Routed-Via` because HTTP headers are ASCII-only; the current adapter exposes the raw header value, so non-ASCII model names may appear encoded. See the [FreeLLMAPI API reference](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/api/01-rest-api.md#response-headers). This reports fallback count, not model quality. Provider failures return a safe failure status; deterministic research outputs remain authoritative.

The status endpoint does not prove the gateway is running, the key is valid, or that a provider has remaining quota. Verify those separately with a small non-sensitive test request.

## Scope and safety boundary

This adapter is a bounded language-model synthesis layer over **supplied research artifacts**. It does not fetch market data, calculate indicators, train model weights, autonomously apply agent proposals, or execute trades. Keep MARKET-MIND-AI in educational research mode. Never send secrets or private data in prompts, and follow the gateway/upstream provider terms and rate limits.
