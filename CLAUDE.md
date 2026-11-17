@AGENTS.md

# Claude Code project notes

This repository is designed to remain usable from multiple coding-agent harnesses. Treat AGENTS.md as the shared project contract and follow its scope, privacy, provenance, and safety boundaries.

## Runtime and validation

- The application runtime is ordinary Python/FastAPI, React/Vite, SQLite, and Docker Compose. It does not depend on Claude Code, Claude APIs, or a Claude-specific SDK.
- Before changing code, inspect the relevant module and tests. Run the documented backend tests and frontend build for the affected area.
- For the optional n8n integration, use `docker compose --profile n8n up -d` only when the operator explicitly configures the local n8n service. Keep workflow drafts inactive; require human review and importer authorization. Never activate or execute imported workflows.
- Never put API keys, reviewer tokens, or provider credentials in source files, prompts, frontend variables, workflow exports, or commits. Use local secret management.
- Do not claim a deployment, live integration, or runtime check succeeded unless the actual target environment was tested.

## Skills

Claude Code skills are mirrored under `.claude/skills/`. Use only the skill relevant to the current task. The portable source skill catalog remains under `.agents/skills/`.
