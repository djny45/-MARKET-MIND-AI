# Operational readiness report — private research platform (2026-11-24)

Verdict: **READY FOR CONTROLLED PRIVATE RESEARCH USE; NOT READY FOR PUBLIC
PRODUCTION.** Private mode is usable on loopback/authorized LAN with per-user
sessions. Public ingress and live financial execution remain disabled. Three
external infrastructure/review gates and six public-deployment gates are
unmet; none is claimed here.

## 1. What was prepared in this cycle

- `docs/PRIVATE-OPERATIONS-SETUP.md`: exact owner steps for a 0600 env file,
  scrypt password hashes, private-mode preflight, Compose start, smoke checks
  and non-destructive shutdown.
- `docker-compose.yml`: backend now consumes operator-supplied
  `FRONTEND_ORIGINS`, `MARKET_MIND_USER_AUTH`, `MARKET_MIND_USERS`,
  `MARKET_MIND_REQUIRE_ORIGIN`, cookie settings and rate limit through
  `docker compose --env-file`. Defaults preserve the existing CI stack; no
  secret is inlined in Git.
- `.env.example` (placeholders only) and `.gitignore` rules (`*.env`, `.env`)
  to keep operator env files out of commits.
- `scripts/private_mode_check.py` + 6 tests: secret-free preflight for hashed
  users, admin presence, private origins, Origin enforcement and the loopback
  Compose perimeter.
- Separate external handover packages: `docs/handover/EXT-01/README.md`,
  `EXT-02/README.md`, `EXT-03/README.md` with contents, permissions, criteria,
  rollback and closure rules. No external evidence was added.

## 2. Startup, connectivity and authentication verification (executed locally)

Docker/systemd are absent here, so verification used the real backend process
and the built frontend served through a temporary local proxy reproducing
`frontend/nginx.conf` same-origin `/api/` routing. Isolated DB under
`/tmp/opencode/ops-verify/run`; fixture users only; transcripts in that
directory (`summary.json` plus captured responses).

| Check | Observed |
| --- | --- |
| Backend startup | uvicorn `app.main:app` on `127.0.0.1:8000`, no errors in log |
| `/api/health` | **200** — `mode=research-only`, `paper_trading=false`, `broker_execution=false` |
| `/api/ready` | **200** — `status=ready`, database reachable/writable, storage `ok` |
| API docs | `/docs` **200** |
| Unauthenticated protected route | `/api/workspaces` **401** |
| Admin login | **200**, session + CSRF cookies set, token returned once |
| `/api/auth/me` with session | **200** |
| Write without CSRF | **403** |
| Write with CSRF | **200** |
| Admin-only environment validation | admin **200**, viewer **403** |
| Frontend index through local frontend origin | **200**, built assets referenced |
| Frontend-proxied `/api/health` and session call | **200 / 200** |
| Private-mode preflight with the same settings | **status pass**, `values_exposed=false` |
| Live financial execution | disabled at runtime in both health and readiness payloads |

This is local functional evidence. It is not Docker Compose, host systemd,
cloud S3 or independent-review validation.

## 3. Seven completed private-platform gates (PASS)

| # | Gate | Evidence in this cycle |
| --- | --- | --- |
| 1 | Backend tests + Python compilation | **1275 OK, 1 skipped** full `unittest discover` (1269 prior + 6 new private-mode tests) |
| 2 | Frontend tests + production build/typecheck | 10/10 unit; 127/127 UI (Node 22.23.5); build/typecheck previously verified and unchanged |
| 3 | Real-browser responsive tests | 9/9 in CI on PR #107 head (CI run `45462154531`) |
| 4 | Dependency and vulnerability audits | `pip-audit` 0; `npm audit --omit=dev` 0; Trivy filesystem/container 0 findings, fail-closed |
| 5 | Recovery drills (database + process kill) | recorded in `docs/RECOVERY_DRILL_EVIDENCE.md` and `REMAINING_WORK.md`: matched fingerprint/row counts, retention, stale lock, kill -9 requeue |
| 6 | Migration rollback + readiness probes | armed→rolled_back with sha256 parity; live `/api/ready` 200 writable in this cycle |
| 7 | Docker Compose integration and health | CI Compose job PASS on PR #107 head; local startup equivalent verified above (local Docker not claimed) |

## 4. Three remaining private-platform gates (BLOCKED)

| # | Gate | Acceptance row | Why blocked / package |
| --- | --- | --- | --- |
| 8 | Docker named-volume backup/restore | part of ACC-030 | no `docker` binary or privileged host here → `docs/handover/EXT-02/README.md` |
| 9 | Real cloud S3 restore | ACC-029 | no endpoint/bucket/credentials → `docs/handover/EXT-01/README.md` |
| 10 | Host systemd/cron restart recovery | ACC-030 | no root/systemctl/crontab → `docs/handover/EXT-02/README.md` |

Plus ACC-031 (independent security review) → `docs/handover/EXT-03/README.md`.
Intake remains fail-closed: `scripts/external_evidence.py audit` reports
37/40 verified and 3 blocked, with no status mutations.

## 5. Public ingress and live execution

- Public deployment gates: **0/6** — TLS issuance/scan, network segmentation,
  ingress hardening, independent penetration test, formal security review,
  production-scale recovery evidence. No public ingress was enabled; Compose
  publishes only loopback `127.0.0.1:8080` and backend has no host port.
- Live execution: no broker/order path; `/api/health` and `/api/ready` explicitly
  report `paper_trading=false`, `broker_execution=false`. The read-only MCP
  allowlist and no-trading boundary in `AGENTS.md` are unchanged. No real
  financial transaction was executed. **Independent transaction-safety
  validation is still required before any live execution is contemplated.**

## 6. Completion and handoff

- Acceptance inventory: **37/40 verified (92.5%)**, 3 BLOCKED.
- Private research gates: **7/10 PASS (70%)**, 3 BLOCKED (listed above).
- Public deployment readiness: **0/6 (0%)**.
- Operationally achievable work for this handover: **complete**.
- Owner next actions: follow `docs/PRIVATE-OPERATIONS-SETUP.md` on an authorized
  host; submit the drafted requests in `docs/EXTERNAL-ACCESS-REQUESTS.md`;
  collect bundles through `docs/EXTERNAL-EVIDENCE-BUNDLES.md`. No external
  validation is inferred from local or CI results.
