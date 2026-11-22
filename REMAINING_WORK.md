# REMAINING WORK — evidence-based

This file records work that is **not** complete, with evidence. Nothing here is
claimed as delivered.

## 1. Authentication and authorization — IMPLEMENTED (opt-in)
Evidence: `backend/app/user_auth.py` and `user_session_middleware.py` provide
per-user sessions with scrypt password verification, HttpOnly session cookies,
hashed CSRF tokens, idle/absolute expiry, four roles, and login/logout/me
endpoints. The memory-review endpoint requires the `operator` role. 14 tests.
The deployment-wide bearer token in `api_auth.py` remains as an additional
layer. Limitation: per-resource authorization is coarse (role hierarchy), not a
full policy engine; auth is disabled by default and must be configured by the
operator. TLS ingress is still required before public exposure.

## 2. Rate limiting — BASIC IMPLEMENTATION
Evidence: `backend/app/rate_limit.py` provides an in-process, per-client-IP
limiter enabled by `API_RATE_LIMIT_PER_MINUTE` (disabled by default); health and
readiness are exempt. It is registered in `main.py` and covered by 5 tests.
Limitation: it is single-process only and is not a substitute for ingress/proxy
rate limiting in a distributed deployment. Per-user quotas are not implemented.

## 2b. Environment validation — IMPLEMENTED
Evidence: `backend/app/env_validation.py` validates auth-token length, CORS
origins (no wildcards), startup-recovery and rate-limit settings without
exposing secret values; exposed via `GET /api/environment-validation` and covered
by 5 tests. It is advisory, not a startup gate.

## 3. Distributed / multi-host task execution — NOT IMPLEMENTED (intentional)
Evidence: `docker-compose.yml` runs one `backend` and one `agent-supervisor`
against a single SQLite volume. `ANALYTICAL-AGENT-TASK-LIFECYCLE.md` now states
single-host only. There is no broker, scheduler, or cloud workspace.
Note: expanding this is a deliberate architecture change, not a defect fix.

## 4. Frontend automated tests — PARTIAL
Evidence: `frontend/package.json` now has a `test` script using Node's built-in
`node:test` runner (no new dependency); `frontend/tests/path-utils.test.mjs`
contains 5 passing tests for base-path normalization and HTML rewriting.
Limitation: there is no React component/DOM test runner, so UI behaviour beyond
the build path and CI smoke checks remains untested automatically.

## 5. Licensed live/delayed market data — NOT CONFIGURED (intentional)
Evidence: health responses report `paper_trading: false` and
`broker_execution: false`; `docs/FOUR-MARKET-PLATFORM.md` documents disabled
provider adapters. Historical/synthetic data is used for research.
Impact: no claims about current market prices are permitted.

## 6. Docker Compose and Trivy verification — NOT RUN LOCALLY
Evidence: `docker` and `trivy` binaries are absent in this container. The GitHub
Actions quality workflow remains the authoritative source; its latest run on
`main` (`45003960135`) succeeded.
Impact: clean-host reproducibility is asserted by CI, not by local execution.

## 7. Host-specific operations — PARTIAL
Evidence:
- **Backup/restore drill: EXECUTED 2026-11-22** against `data/market_mind.db`.
  Backup → `status=verified`; restore → `status=restored_and_verified`;
  `PRAGMA integrity_check` = `ok` on source and restored; row counts match.
  Details in `BACKUP_RESTORE_GUIDE.md`; evidence recorded in
  `PROJECT_STATUS.md` (Backup/restore row) and this file.
- Not yet done: retention-policy repetition, off-host storage, migration
  rollback drills, alerting-on-incident reproduction, TLS ingress hardening.

## 8. Pull request housekeeping — reconciled 2026-11-22
Evidence: `gh pr list --state open` now returns 35 PRs (29 drafts, 6 non-draft).
- Merged in this session: #3, #19, #23, #41, #26, #28 (+ the 11 research-loop PRs).
- Closed as superseded by new work: #2, #29, #30, #34, #36, #43, #44, #46, #47,
  #48, #49, #66.
- Remaining open: mostly DRAFTs (29) from older work needing review;
  #31 (open, docs refresh) was left open because it is independently valuable
  but conflicts with current `main`; `main` was reset to `origin/main`
  (`57930e0`) because local `main` had an unmergeable Trivy-workflow commit
  (`77467d0`).
- Trivy CI file committed locally (`feat/trivy-fs`); blocked from pushing by the
  OAuth `workflow` scope.

## 9. New Trivy CI gap — COMMITTED LOCALLY, BLOCKED FROM PUSH
Evidence: commit `1827be8` ("ci(security): add Trivy filesystem scan workflow")
on `feat/trivy-fs`. OAuth app rejects pushes to `.github/workflows/*` without the
`workflow` scope. Documented in `docs/TRIVY-CI.md`; run Trivy locally with the
documented commands (`trivy fs --scanners misconfig,secret --severity MEDIUM,HIGH,CRITICAL .`)
and review any findings.

## 10. Imported execution code — INTENTIONALLY INERT
Evidence: `third_party/FinceptTerminal/` (AGPL-3.0), `third_party/freqtrade/`
(GPL-3.0), and AutoHedge signing/order modules are local reference copies; no
imports, builds, or executions were wired into the application. The Camofox
browser is isolated, localhost-only, and has no credentials.
Impact: this is a deliberate security boundary, not pending work.
