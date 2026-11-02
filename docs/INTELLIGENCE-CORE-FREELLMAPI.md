# FreeLLMAPI integration (shared intelligence core)

MARKET-MIND-AI can optionally use a locally running FreeLLMAPI gateway for bounded
research summarization. FreeLLMAPI is an external service; this repository does
not install it, embed provider keys, or start it automatically.

## Configure

1. Install and start FreeLLMAPI separately on the same machine as the backend.
2. In FreeLLMAPI's dashboard, configure provider credentials and obtain its
   unified API key. Keep the key private.
3. Set these environment variables for the backend process:

```bash
INTELLIGENCE_CORE_ENABLED=true
INTELLIGENCE_CORE_PROVIDER=freellmapi
FREELLMAPI_BASE_URL=http://127.0.0.1:3001
FREELLMAPI_API_KEY=<your-private-unified-key>
FREELLMAPI_MODEL=<model-id-configured-in-FreeLLMAPI>
```

The integration calls `POST /v1/chat/completions` with Bearer authentication.
The URL is deliberately restricted to loopback HTTP (127.0.0.1 or ::1) to avoid
sending research payloads or credentials to arbitrary remote endpoints. If
FreeLLMAPI is hosted on another machine, use a secure network architecture
review rather than weakening this check.

## Verify

- `GET /api/intelligence-core` reports the selected provider and configuration
  state. It does not health-check the gateway or expose credentials.
- Research synthesis remains optional. When the gateway is unavailable or
  returns unusable output, deterministic research reports remain authoritative.
- Only the already-provided research JSON is summarized; this integration does
  not fetch market data, place orders, perform autonomous learning, or trade.
- Do not commit API keys or place them in frontend environment variables.
