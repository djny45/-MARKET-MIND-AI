# REMAINING WORK — evidence-based

This file records work that is **not** complete, with evidence. Nothing here is
claimed as delivered.

## 1. Authentication and authorization — PARTIAL
Evidence: `backend/app/api_auth.py` provides an **optional deployment-wide**
bearer token (`API_AUTH_REQUIRED`, `API_AUTH_TOKEN`, 32+ chars). `main.py:98`
registers it. `main.py:917` states reviewer identity is self-reported in the
prototype. There is no per-user identity, role model, or per-resource
authorization.
Impact: public deployment remains blocked (already stated in README and
PROJECT_STATUS.md).

## 2. Rate limiting — NOT IMPLEMENTED
Evidence: no rate-limit middleware or dependency in `backend/app`; CORS and the
optional bearer middleware are the only request-gating layers.
Impact: abuse protection must be provided at ingress until implemented.

## 3. Distributed / multi-host task execution — NOT IMPLEMENTED (intentional)
Evidence: `docker-compose.yml` runs one `backend` and one `agent-supervisor`
against a single SQLite volume. `ANALYTICAL-AGENT-TASK-LIFECYCLE.md` now states
single-host only. There is no broker, scheduler, or cloud workspace.
Note: expanding this is a deliberate architecture change, not a defect fix.

## 4. Frontend automated tests — NOT IMPLEMENTED
Evidence: `frontend/package.json` scripts are only `dev` and `build`; no test
runner or test files exist in `frontend/`.
Impact: UI regressions are caught only by the production build and CI smoke
checks.

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

## 7. Host-specific operations — NOT VERIFIED
Evidence: `PROJECT_STATUS.md` still lists host backup/restore drills, retention
policy, migration rollback, incident procedures, alert delivery and TLS ingress
as outstanding.
Impact: deployment readiness is limited to private, operator-managed hosts.

## 8. Stale pull requests — 45 OPEN
Evidence: `gh pr list --state open` returns 45 PRs, 43 DRAFT. PR #31 conflicts
with current `main` (stale PROJECT_STATUS wording); PR #19 adds dependabot and
free-cloud docs and is mergeable. These pre-existing PRs were not merged as part
of this work because their changes are superseded by current `main` or require
independent review.

## 9. Imported execution code — INTENTIONALLY INERT
Evidence: `third_party/FinceptTerminal/` (AGPL-3.0), `third_party/freqtrade/`
(GPL-3.0), and AutoHedge signing/order modules are local reference copies; no
imports, builds, or executions were wired into the application. The Camofox
browser is isolated, localhost-only, and has no credentials.
Impact: this is a deliberate security boundary, not pending work.
