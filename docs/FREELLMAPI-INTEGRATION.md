# Inception Labs Mercury integration

MARKET-MIND-AI uses **Inception Labs Mercury-3** as the default shared intelligence provider. It calls the official OpenAI-compatible chat-completions endpoint directly; no Ollama server or local gateway is required.

## 1. Configure the backend

Set these environment variables for the backend process:

```dotenv
INTELLIGENCE_CORE_ENABLED=true
INTELLIGENCE_CORE_PROVIDER=mercury
INCEPTION_API_KEY=your_inception_labs_api_key
INCEPTION_MODEL=mercury-3
```

The adapter sends a non-streaming chat-completions request to the fixed endpoint:

`https://api.inceptionlabs.ai/v1/chat/completions`

It uses the Bearer API key in the backend request header and sends the prompt in the `messages` field. The model defaults to `mercury-3`.

**Keep the API key private.** Store it in your deployment's secret/environment-variable settings or an untracked local `.env` file. Never paste it into GitHub source, commits, frontend code, screenshots, or public issues. Do not share it in ChatGPT. If it has already been exposed, revoke it in the provider dashboard and create a replacement.

Restart the backend after setting the variables. The status endpoint reports configuration only; it does not validate the API key, provider quota, or network access.

## 2. Request and response behavior

- `GET /api/intelligence-core` reports configured provider state without contacting Mercury.
- `POST /api/intelligence-core/synthesize` submits bounded caller-supplied research JSON for synthesis.
- A successful completion reports `provider: inceptionlabs_mercury` and `status: completed`.
- Provider errors return a safe failure status; the deterministic report remains authoritative.
- API keys are not returned in status or synthesis results.

## 3. Existing alternate provider

The legacy `freellmapi` provider remains available for users who explicitly configure a local FreeLLMAPI gateway using `INTELLIGENCE_CORE_PROVIDER=freellmapi`. Its loopback-only restrictions and environment variables remain documented in the adapter and prior project history. Mercury is the default and does not require that gateway.

## Scope

The Mercury integration is a bounded language-model synthesis layer over **supplied research artifacts**. It does not fetch market data, calculate indicators, train model weights, autonomously apply agent proposals, or execute trades. Provider output is not independently verified; treat it as an analysis draft and verify claims against source evidence.

## 4. Diagnosing "Upstream request failed: Model is unavailable"

That message originates in the **notebook/harness upstream**, not in
MARKET-MIND-AI. This repository contains no notebook-side model router: the
550 profiles share one optional inference core (`backend/app/intelligence_core.py`)
and every workflow node is routed to a deterministic Python handler by default.
`GET /api/worker-runtime` reports `llm_inference_enabled: false`, so this
application can never be the source of that upstream error.

Check in this order:

1. **Provider configuration** — `GET /api/intelligence-core` reports the
   configured provider and model without contacting the provider or exposing
   the API key. If it reports `provider: not_configured`, the notebook is
   trying to use a model that this backend has not been configured for.
2. **Model name** — for Mercury the supported default is `mercury-3`
   (`INCEPTION_MODEL`). A stale or misspelled model name in the notebook or
   harness produces "Model is unavailable". Do not silently switch providers.
3. **Rate limits / quota** — an exhausted provider quota surfaces here as
   `status: provider_unavailable`; the deterministic report remains
   authoritative. Re-check the provider dashboard; never log or return keys.
4. **Notebook service** — if the backend status is healthy but the notebook
   still reports the error, the failure is in the notebook's own upstream
   routing and must be fixed in that service's configuration.

`POST /api/intelligence-core/synthesize` uses a bounded timeout, bounded input
and safe failure statuses (`provider_unavailable`, `invalid_provider_response`).
It never retries blindly, never changes deterministic calculations, and never
exposes credentials. The platform remains fully usable in its deterministic
offline mode without any provider configured.
