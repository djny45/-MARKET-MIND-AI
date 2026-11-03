# FreeLLMAPI integration

MARKET-MIND-AI contains a FreeLLMAPI adapter in `backend/app/freellmapi_adapter.py`. It connects the **single shared intelligence core** to the separately running FreeLLMAPI OpenAI-compatible gateway. It does not install or host FreeLLMAPI inside this repository, and it does not create one model per analytical worker.

## Upstream project and docs

- Repository: https://github.com/tashfeenahmed/freellmapi
- Install guide: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/install/01-install.md
- API reference: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/api/01-rest-api.md
- Client guide: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/clients/01-agent-clients.md

## 1. Run FreeLLMAPI separately

FreeLLMAPI requires its own runtime (Docker, Node.js, or supported desktop app) and provider configuration. Start the gateway, configure provider keys in its dashboard, and copy the unified API key from its Keys page. The default local gateway is `http://127.0.0.1:3001`; its OpenAI-compatible API is `/v1`.

**Important:** FreeLLMAPI is a gateway, not a source of unlimited guaranteed inference. Upstream provider quotas, availability, and terms still apply. Do not commit gateway/provider credentials, expose them in screenshots, or put them in public issues.

## 2. Configure MARKET-MIND-AI

Set these environment variables for the backend process:

```dotenv
INTELLIGENCE_CORE_ENABLED=true
INTELLIGENCE_CORE_PROVIDER=freellmapi
FREELLMAPI_BASE_URL=http://127.0.0.1:3001
FREELLMAPI_API_KEY=replace-with-your-local-unified-key
FREELLMAPI_MODEL=auto
```

Use `auto` to let FreeLLMAPI choose a routed model, or use a model ID returned by its `GET /v1/models` endpoint. The adapter accepts either a gateway root URL (for example `http://127.0.0.1:3001`) or a base URL ending in `/v1`. It sends a Bearer token to `/v1/chat/completions` and requests a non-streaming OpenAI-compatible response.

Restart MARKET-MIND-AI's backend after setting the environment variables.

## 3. Verify the gateway before connecting MARKET-MIND-AI

Run this on the same host where FreeLLMAPI is listening. Replace the placeholder locally; do not paste the key into GitHub or chat:

```bash
curl -sS http://127.0.0.1:3001/v1/models \
  -H "Authorization: Bearer YOUR_FREELLMAPI_UNIFIED_KEY"
```

A successful response should be an OpenAI-style model-list JSON response. This verifies the gateway endpoint and key, not that every upstream model is available.

Then check MARKET-MIND-AI configuration:

```bash
curl -sS http://127.0.0.1:8000/api/intelligence-core
```

This status endpoint reports configuration only; it does **not** call FreeLLMAPI or verify the key. To verify an actual inference connection, submit a small supplied-research synthesis through `POST /api/intelligence-core/synthesize`. The returned provider status distinguishes a successful completion from an unavailable or invalid response.

## Docker networking

If MARKET-MIND-AI and FreeLLMAPI run in separate containers, `127.0.0.1` inside MARKET-MIND-AI refers to that container itself. The current adapter deliberately restricts FreeLLMAPI to loopback addresses, so a Docker service hostname such as `http://freellmapi:3001` is rejected. Keep both services on the same host using loopback for now; do not expose the gateway publicly to bypass this restriction. A future container-network option should require an explicit trusted-network allowlist and dedicated tests.

## Scope and safety boundary

FreeLLMAPI is an optional language-model synthesis provider for **already supplied research artifacts**. It does not fetch market data, calculate indicators, train model weights, apply agent proposals, or execute trades. MARKET-MIND-AI remains research/educational-only; deterministic reports remain authoritative when synthesis is unavailable.