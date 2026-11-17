# Coding-agent and harness compatibility

## Design rule

MARKET-MIND-AI is an ordinary application stack, not an extension that must execute inside one AI coding harness. The same checked-out repository can be developed with Claude Code, Codex, GitHub Copilot, Cursor, or another tool that can edit files and run the documented shell commands. The deployed application remains FastAPI + React/Vite + SQLite + Docker Compose; changing the coding harness must not change runtime behavior.

No coding harness is guaranteed to load every instruction or skill format automatically. Use the adapters below and verify instruction discovery in the chosen tool.

## Instruction and skill locations

| Harness | Project instructions | Skill guidance |
|---|---|---|
| Codex / AGENTS-compatible tools | `AGENTS.md` | Portable catalog in `.agents/skills/` |
| Claude Code | `CLAUDE.md` imports `AGENTS.md` | Claude-discoverable mirror in `.claude/skills/` |
| GitHub Copilot | `.github/copilot-instructions.md` | Follow relevant portable skill manually |
| Cursor | `.cursor/rules/market-mind.mdc` | Follow relevant portable skill manually |
| Other harnesses | Configure its project-rules feature to include `AGENTS.md` | Point it to the relevant `.agents/skills/<skill>/SKILL.md` |

A harness may require a newer version or a setting to load a given instruction file. Confirm the files appear in its project context. Skills are guidance, not installed tools: they do not create MCP servers, credentials, external accounts, or provider access.

## Shared MCP tools

The repository includes a local stdio server using the official open-source MCP Python SDK. Its tools are deliberately read-only:

- `market_mind_capabilities` — describes project capabilities and hard execution boundaries.
- `list_engineering_skills` and `read_engineering_skill` — expose a fixed engineering/n8n skill allowlist, never arbitrary filesystem paths.
- `validate_n8n_workflow_json` — validates supplied workflow JSON locally; it does not import or run it.

Install the backend dependencies once:

```bash
python -m pip install -r backend/requirements.txt
```

The checked-in launch configurations are:
- Claude Code: root `.mcp.json`, the project-scoped MCP configuration.
- GitHub Copilot: root `.mcp.json`, the portable workspace-root format. Copilot's workspace-root configuration can be managed through its MCP Servers customization; the experimental workspace-root setting affects whether the guided Add Server flow offers this location.
- Cursor: `.cursor/mcp.json`, the documented project-specific configuration location.
- Codex: `.codex/config.toml`, the project-scoped configuration (Codex loads it only after the repository is trusted).

The root `.mcp.json` intentionally omits `cwd` because Copilot's workspace-root portable configuration does not expose a working-directory field. The server resolves its own backend import path relative to the script, so it can start from the workspace root. Cursor and Codex configurations set the working directory explicitly. These launch the same `backend/app/mcp_server.py` process over stdio.

If your Python executable is named `python3` (or `py` on Windows), change only the `command` value in the client configuration. Install the backend dependencies in the same environment where the harness runs. For remote/SSH/dev-container harnesses, install Python dependencies in that remote environment too. Restart/reload the harness and verify that it discovers the four tools; configuration presence alone does not prove the host can launch the process.

Official setup references: [Claude Code MCP](https://docs.anthropic.com/en/docs/claude-code/mcp), [VS Code/Copilot MCP configuration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration), [Cursor MCP configuration](https://cursor.com/docs/mcp), and [Codex project configuration](https://learn.chatgpt.com/docs/config-file/config-basic).

The server is local to the coding host; it is not a remotely hosted MCP endpoint. The tools do not have repository-write, network-fetch, n8n-import, workflow activation/execution, or brokerage capabilities. Tool discovery is not proof that an n8n instance or live market-data provider is configured. Do not add secrets to MCP configuration.

## Run the application independently of the harness

Prerequisites: Docker Engine and Docker Compose plugin. From the repository root:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

For the optional local n8n service:

```bash
docker compose --profile n8n up --build -d
```

Follow [the private deployment guide](PRODUCTION-DEPLOYMENT.md) for n8n owner setup and server-side environment configuration. The n8n editor is loopback-only in this Compose profile. Do not expose it publicly. Do not paste secrets into any coding assistant.

## Required verification before calling a deployment portable

1. Confirm the harness has loaded its project instructions.
2. Run `docker compose config --quiet`.
3. Run backend tests and frontend production build using [the development guide](DEVELOPMENT.md).
4. Start the default Compose stack and check `/api/ready`.
5. If n8n is intentionally enabled, check its health endpoint and backend-to-n8n network reachability.
6. Test workflow validation, reviewer authorization, importer authorization, inactive-state verification, and uncertain-outcome handling.
7. Report the exact commit, commands, CI run, target environment, and any unverified integration.

CI in GitHub Actions is useful evidence but does not prove a user's own VPS, cloud host, or local Docker installation is configured correctly.

## Security and operational boundaries

- Keep n8n disabled unless explicitly configured.
- Require human review and a separate importer role before import.
- Imported workflows must remain inactive. Do not add activation or execution automation.
- Keep reviewer tokens, n8n API keys, and all provider credentials server-side in a secret manager or uncommitted local environment file.
- Never expose the backend API or n8n editor directly to the public internet without a separately reviewed authentication and TLS ingress layer.
- Do not add broker order routing or brokerage execution.
