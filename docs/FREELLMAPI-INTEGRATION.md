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
