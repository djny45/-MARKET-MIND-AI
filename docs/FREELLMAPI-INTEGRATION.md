# FreeLLMAPI integration

MARKET-MIND-AI already contains a FreeLLMAPI adapter in `backend/app/freellmapi_adapter.py`. This integration connects the existing **single shared intelligence core** to a separately running FreeLLMAPI OpenAI-compatible gateway. It does not install or host the gateway inside GitHub, and it does not create one model per analytical worker.

## 1. Run FreeLLMAPI separately

FreeLLMAPI requires its own runtime (Docker or Node.js) and provider configuration. Follow its upstream installation guide:

- Project: https://github.com/tashfeenahmed/freellmapi
- Install guide: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/install/01-install.md
- API guide: https://github.com/tashfeenahmed/freellmapi/blob/main/docs/api.md

Start its dashboard, configure one or more provider/model entries, and copy the unified API key from its Keys page. The gateway's OpenAI-compatible endpoint is normally `http://127.0.0.1:3001/v1`.

**Do not put the gateway API key in GitHub source, commit history, screenshots, or public issues.** Store it in a local environment file or your deployment platform's secret store.

## 2. Configure MARKET-MIND-AI

Set these environment variables for the backend process:

```dotenv
INTELLIGENCE_CORE_ENABLED=true
INTELLIGENCE_CORE_PROVIDER=freellmapi
FREELLMAPI_BASE_URL=http://127.0.0.1:3001
FREELLMAPI_API_KEY=replace-with-your-local-unified-key
FREELLMAPI_MODEL=auto
```

Use the model identifier supported by the configured FreeLLMAPI gateway (for example `auto` or a model ID shown in its dashboard). The adapter appends `/v1/chat/completions`, sends a Bearer token, and requests non-streaming OpenAI-compatible chat completions.

Restart the backend after setting the variables.

### Docker networking

If MARKET-MIND-AI and FreeLLMAPI are separate containers, `127.0.0.1` inside MARKET-MIND-AI points to MARKET-MIND-AI itself, not the FreeLLMAPI container. Use a shared Docker network and the FreeLLMAPI service name as the host, such as `http://freellmapi:3001`, **only if** the service is reachable from that network. The current adapter intentionally permits loopback hosts only, so a service-name/container-network setup will be rejected until the integration's network trust policy is deliberately expanded. Do not expose the gateway publicly just to work around this restriction.

For a backend and gateway running on the same machine, loopback is the intended supported setup.

## 3. Verify

- `GET /api/intelligence-core/status` reports provider configuration without making a provider request. A configured result means **configured, not health-checked**.
- Run the research synthesis endpoint/workflow with a small, already-computed research payload to test a real completion.
- If FreeLLMAPI is offline or returns an invalid response, synthesis returns a provider failure status and the deterministic research report remains authoritative.

## Scope and safety boundary

FreeLLMAPI is an optional text-synthesis provider for supplied research artifacts. It does not provide market data, compute indicators, train model weights, apply agent proposals, or execute trades. Keep the gateway key private and use provider accounts/quotas in accordance with their terms.
