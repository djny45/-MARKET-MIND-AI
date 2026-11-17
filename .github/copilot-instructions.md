# MARKET-MIND-AI coding-agent instructions

Follow the repository-level `AGENTS.md` as the shared project contract. Read only the task-relevant skill under `.agents/skills/`; do not load the entire catalog.

The app is harness-independent: FastAPI, React/Vite, SQLite and Docker Compose run as normal services and do not require a particular coding assistant or model provider. Preserve provider-neutral interfaces and do not introduce harness-specific runtime dependencies into application code.

For the optional n8n integration, keep it opt-in, local/private, inactive by default, and gated by human review plus importer authorization. Never activate or execute workflows. Keep credentials in deployment secret management, never in code, prompts, frontend bundles, workflow exports, or commits.

The root `.mcp.json` provides the shared local read-only MCP server. Install `backend/requirements.txt`, restart/reload the Copilot harness, and verify tool discovery. Its fixed tools expose project capabilities, allowlisted engineering skills, and n8n structural validation only; no filesystem writes, external network calls, workflow import/activation/execution, or brokerage actions are exposed.

Inspect existing code and tests before editing. Run relevant tests and report exactly what was and was not verified. Do not claim live deployment or external connectivity based only on unit tests.
