# Private operational launch report — 2026-11-24

Verdict: **LAUNCHED AND USABLE for controlled private research** on loopback
with per-user sessions. **Public ingress and live financial execution remain
disabled.** Three external gates (EXT-01/02/03) and six public-deployment gates
are still unmet; no external evidence was fabricated.

## 1. Git and PR verification (not assumed merged)

| Item | Verified value |
| --- | --- |
| Local HEAD at launch start | `da551267af5d12fceac83ef1ed77738cee2cf8ca` on `feature/alpine-backend-runtime`, clean tree |
| `git ls-remote origin refs/heads/main` | `1a13bfe28974ebdf2877ba0180889122aeafd7e0` — the PR stack is not merged into main |
| PR #107 | `state=OPEN`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`, head matches the local launch HEAD, base `feature/phase5-risk-resolution` |
| CI | run `45467690396`: 7/7 required jobs SUCCESS (Backend, Frontend, Compose, Dependency audit, Trivy filesystem, Container scan, Real browser) |

## 2. Private-mode launch actually executed

Docker/systemd are unavailable in this environment, so the **documented private
configuration** (`docs/PRIVATE-OPERATIONS-SETUP.md` §§2–4) was applied to a real
uvicorn backend with an isolated database under `/tmp/opencode/ops-launch`, plus
the built frontend served through a temporary local proxy reproducing
`frontend/nginx.conf` same-origin `/api/` routing. Fixture users only; no
production database and no external service.

- Env file: `/tmp/opencode/ops-launch/private.env` (0600, generated from scrypt
  hashes, `MARKET_MIND_USER_AUTH=true`, `MARKET_MIND_REQUIRE_ORIGIN=true`,
  private loopback origin). `private_mode_check.py` passes with these settings.
- Backend log: `/tmp/opencode/ops-launch/backend.log` — startup complete,
  **0 error/traceback/exception markers**, **0 secret markers**, 27 request lines.
- Live results: `/tmp/opencode/ops-launch/live-results.json` — **18/18 checks HTTP 200**.
- All test ports were released after the run (`ss -ltn`: 8000/8080 free).

## 3. Connectivity, authentication and dashboards

| Check | Evidence |
| --- | --- |
| `/api/health` | 200 — `mode=research-only`, `paper_trading=false`, `broker_execution=false` |
| `/api/ready` | 200 — `status=ready`, database writable, storage `ok` |
| Admin login / `/api/auth/me` | 200 / 200 — session created, tokens returned once |
| Protected route without session | 401 |
| Write without / with CSRF | 403 / 200 |
| Admin-only env validation | admin 200, viewer 403 |
| Frontend index + proxied health/session | 200 / 200 / 200 |
| Dashboard endpoints | `/api/backup/status`, `/api/security/audit-events`, per-worker research-quality dashboard, `/api/research/timeline`, `/api/analytics/performance`, `/api/providers/status` — all 200 |
| Application logging | `/api/security/audit-events` returned 6 redacted events with `secret_values_exposed=false`; backend log clean |

## 4. Agent profiles, orchestration, skills, memory, research, analytics

| Area | Actual evidence |
| --- | --- |
| Registered profiles | `/api/workers?limit=550` → **count 550**; `registry_manifest()` → `agent_count=550`, `department_count=20`, `valid=true`, digest `e4cb69c1e92ef342…`; `/api/analytical-agents/runtime` → `agent_count=550` |
| Orchestration | `/api/analytical-agent-supervisor/status` → `registered_agent_count=550`, `dispatch_mode=persistent_sqlite_polling`, `status=not_started` (no daemon launched here); `/api/agent-network` → `mode=deterministic_message_bus`; `/api/agent-network/activity` → 200; `/api/analytical-agents/learning-overview` → 200 |
| Skills | `/api/skills` → **325** available playbooks, `paper_trading=false`, `broker_execution=false`; catalog/integrity/cadence/promotion suites pass |
| Memory | per-worker `/api/workers/{id}/memory` → 200 (0 records on the isolated DB); memory, ownership and runtime suites pass |
| Research | `/api/research/timeline?symbol=BTCUSD` → 200; orchestrator, dashboard, backtest, benchmark and export suites pass |
| Analytics | `POST /api/analytics/performance` → 200 with computed Sharpe/drawdown/volatility metrics on fixture values |
| Targeted test suite | **285 tests OK** across 33 worker/skill/memory/research/orchestration/agent/MCP/analytics/audit modules |
| Full regression suite | **1275 OK, 1 skipped** (`unittest discover -s backend/tests -q`) on this HEAD; CI Backend job also SUCCESS |

## 5. Read-only MCP and no-trading boundary

- `backend/app/mcp_server.py` registers **exactly 6 tools**:
  `market_mind_capabilities`, `mcp_server_diagnostics`, `list_engineering_skills`,
  `read_engineering_skill`, `validate_n8n_workflow_json`, `browser_research_read`.
- Module introspection found **no** order/trade/broker/execute/payment/transfer/
  import symbols. The local read-only server is an allowlist; adding
  filesystem/shell/network/broker tools requires a separate security design and
  explicit authorization (`AGENTS.md`).
- The separate Camofox browser REST server at `127.0.0.1:9377` is **not running**
  here (`http=000`); no browser research action is claimed in this launch.
- `/api/health` and `/api/ready` both report `broker_execution=false` and
  `paper_trading=false`; no brokerage key, wallet or real-money path was
  configured, and no financial transaction was executed. Independent
  transaction-safety validation is still required before any live execution.

## 6. Public ingress and deployment status

- `config_preflight.py --root .`: **status pass**, 12 checks, 0 failures,
  `values_exposed=false`, including `backend_not_host_published`,
  `published_ports_loopback` and `services_unprivileged`.
- Compose publishes only `127.0.0.1:8080` and `127.0.0.1:5678` (optional n8n);
  backend has no host port. No public ingress or TLS endpoint was enabled.
- GitHub deployments API: **0** production deployments. Public gates remain
  **0/6**: TLS issuance/scan, segmentation, ingress hardening, independent
  penetration test, formal security review, production-scale recovery evidence.

## 7. Completion and boundaries

- Acceptance inventory: **37/40 verified (92.5%)**, 3 BLOCKED
  (ACC-029/030/031); intake validator reports no closure_allowed bundles.
- Private research gates: **7/10 PASS (70%)**; remaining 3 are EXT-01/02/03.
- Operationally achievable launch work: **complete**. The platform is usable
  as a controlled private research terminal; it is **not** a public production
  release. Owner handoff: `docs/PRIVATE-OPERATIONS-SETUP.md`, external packages
  in `docs/handover/EXT-01|EXT-02|EXT-03/README.md`, and the fail-closed intake
  in `docs/EXTERNAL-EVIDENCE-BUNDLES.md`.
