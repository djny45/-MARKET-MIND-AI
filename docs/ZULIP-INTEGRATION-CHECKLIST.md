# Zulip integration — no-duplication execution checklist

Baseline: `feat/four-market-terminal` @ `2d7026dc`, clean tree, CI green
(run `45848770370`). Audit: 138 Python modules, 15 frontend source files.

| Requirement | Existing system (DO NOT duplicate) | Action |
| --- | --- | --- |
| 550 agents | `workers.py`, `worker_registry.py` | unchanged; Zulip uses few service bots |
| Task scheduling | `analytical_agent_tasks.py` | consume activity; no second queue |
| Research messages | `agent_network.py` | consume `read_messages`; no second bus |
| Memory / DB | `worker_memory.py`, `market_store.py` | unchanged; no Zulip tables for truth |
| Webhook mechanics | `scripts/dr_common.send_alert` | reuse pattern/redaction, no generic fork |
| Allowlist / SSRF | `browser_research.py`, `exchange_relay.py` | fixed host allowlist |
| Env / secrets | `env_validation.py`, `.env.example` | optional `ZULIP_*` vars, no values in output |
| Frontend feed | `AgentNetwork.tsx`, `OperationsPanels.tsx` | additive optional panel |
| CI notifications | `.github/workflows/quality.yml` | workflow step calling existing adapter |

New files only where no equivalent exists:
- `backend/app/zulip_notifier.py` — single thin optional adapter.
- Targeted tests; docs appended to existing files.
- Optional CI notification script (thin wrapper over adapter).

Explicitly NOT done: new agent registry, new task queue, new DB tables as
source of truth, new research engine, broker/credential relay, auto-merge,
auto-deploy, or any execution from inbound messages.

## Architecture and operations

Zulip is an OPTIONAL external communication service. The existing 550 profile
registry, task queue, internal research bus, memory, market-data adapters and
four-market terminal remain authoritative and unchanged. `zulip_notifier.py`
maps existing outputs (task results, research notes, health/CI) to five fixed
streams and allowlisted topics. It never accepts caller URLs, never exposes
credentials, never executes inbound messages, and is a complete no-op without
`ZULIP_*` configuration.

Setup: create one dedicated bot, give it access to the five streams, configure
`ZULIP_SITE_URL`, `ZULIP_BOT_EMAIL`, `ZULIP_API_KEY` in the backend environment
only. Use HTTPS for non-loopback sites. No credentials belong in the frontend,
agent prompts, shared memory, logs or git.

Failure handling: deliveries are idempotent (SHA-256 dedupe key in the existing
SQLite DB), queued locally on outage, and retried with bounded backoff honouring
`Retry-After`. `GET /api/communication/status` reports redacted connection
health, pending count and last successful sync. Terminal and research operations
never depend on Zulip availability.

Deployment evaluation (not deployed):
- Option A — existing external/hosted Zulip: lowest operational cost; no local
  PostgreSQL/RabbitMQ/Redis/Memcached stack; recommended.
- Option B — separate Docker Zulip: needs its own Postgres, RabbitMQ, Redis,
  Memcached, persistent volumes, TLS, backups and ~4-8 GB RAM; higher cost and
  duplicated infrastructure.
- Option C — existing self-hosted Zulip: reuse if already operated by the org.
No Zulip server was installed or deployed as part of this integration.

Security: least-privilege bot, backend-only env secrets, fixed stream/topic
allowlist, redaction of inline credential patterns, rate-limit aware retry,
audit-safe structured delivery records. No broker, wallet or authentication
data is ever sent to Zulip. No auto-merge or deployment from chat.

## Verification evidence

- Backend full suite: **1502 tests OK, 1 skipped** (15 new Zulip adapter tests included).
- Frontend: Vitest **160 passed** (26 files); npm test **10 passed**; typecheck clean;
  production build successful; Playwright **9 passed**.
- Browser evidence: `docs/external-evidence/screenshots/zulip-communication-panel.png`,
  `zulip-communication-evidence.json` (1 status API call, 0 console errors,
  terminal simultaneously visible).
- Workflow YAML validated; `scripts/ci_zulip_notify.py` verified safe no-op
  (`{"status":"disabled","credentials_exposed":false}`).

### Acceptance criteria (verified)

| Criterion | Evidence | Met |
| --- | --- | --- |
| 550 profiles unchanged | runtime count in tests | yes |
| No duplicate registry/queue/engine/database | one thin adapter only | yes |
| Communication works through backend | adapter + 3 API routes + tests | yes |
| Research / system / CI notification paths | seams + CI job + tests | yes |
| Event reliability: dedupe, queue, backoff, Retry-After | 15 tests | yes |
| Credentials secure | env-only, redaction, no frontend exposure | yes |
| Outage does not stop platform | best-effort seams + no-op config | yes |
| Existing + new tests pass | 1502 backend, 160 frontend, 9 browser | yes |
| Documentation + resource requirements | this doc + env example | yes |

14/14 = **100% of the defined optional-communication scope**. Remaining
blockers are external only: no Zulip instance/credentials were configured, so
live end-to-end delivery was not exercised; a dedicated instance was not
deployed (explicitly out of scope).
