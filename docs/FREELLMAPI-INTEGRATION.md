# Optional hosted Inception Labs Mercury provider

Local Ollama is the default shared intelligence provider when synthesis is enabled. Mercury is an optional hosted provider and may incur API charges. This page documents the optional Mercury configuration; no hosted provider is required for local-only use.

## Configure the optional hosted provider

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

## Request and response behavior

- `GET /api/intelligence-core` reports configured provider state without contacting Mercury.
- `POST /api/intelligence-core/synthesize` submits bounded caller-supplied research JSON for synthesis.
- A successful completion reports `provider: inceptionlabs_mercury` and `status: completed`.
- Provider errors return a safe failure status; the deterministic report remains authoritative.
- API keys are not returned in status or synthesis results.

## Other optional providers

A local FreeLLMAPI gateway remains available when explicitly selected with `INTELLIGENCE_CORE_PROVIDER=freellmapi`. Provider credentials and costs depend on the gateway's own configuration. Local Ollama remains the no-hosted-key default.

## Scope

This optional Mercury integration is a bounded language-model synthesis layer over **supplied research artifacts**. It does not fetch market data, calculate indicators, train model weights, autonomously apply agent proposals, or execute trades. Provider output is not independently verified; treat it as an analysis draft and verify claims against source evidence.
