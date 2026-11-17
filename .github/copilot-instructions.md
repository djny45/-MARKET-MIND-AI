# MARKET-MIND-AI coding-agent instructions

Follow the repository-level `AGENTS.md` as the shared project contract. Read only the task-relevant skill under `.agents/skills/`; do not load the entire catalog.

The app is harness-independent: FastAPI, React/Vite, SQLite and Docker Compose run as normal services and do not require a particular coding assistant or model provider. Preserve provider-neutral interfaces and do not introduce harness-specific runtime dependencies into application code.

For the optional n8n integration, keep it opt-in, local/private, inactive by default, and gated by human review plus importer authorization. Never activate or execute workflows. Keep credentials in deployment secret management, never in code, prompts, frontend bundles, workflow exports, or commits.

Inspect existing code and tests before editing. Run relevant tests and report exactly what was and was not verified. Do not claim live deployment or external connectivity based only on unit tests.
