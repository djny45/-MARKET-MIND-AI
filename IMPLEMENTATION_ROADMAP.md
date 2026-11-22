# IMPLEMENTATION ROADMAP — verified status

Status values: **DONE** (verified in this session), **EXISTING** (present and
verified, not changed here), **REMAINING** (not implemented; evidence in
`REMAINING_WORK.md`).

## Stage 0 — Baseline audit — DONE
- Inspected tracked tree, branches, commits, docs, modules and tests.
- Created `FINAL_COMPLETION_AUDIT.md` with measured values.
- Verified 550 workers, 414 skill definitions, 0 integrity issues.

## Stage 1 — Documentation and build reconciliation — DONE
- `frontend/scripts/build.mjs` honors `VITE_BASE_PATH`; generated HTML rewritten.
- Dead Vite config/typings removed; framework-neutral `env.d.ts` added.
- Configure button wired to a read-only settings dialog (no placeholder action).
- Stale endpoint/status/tool-count/supervisor documentation corrected.
- Verified: 894 backend tests pass; root and project-site builds pass.

## Stage 2 — Skill and worker integrity — DONE
- `app/skill_integrity.py`: catalog, reference-skill and worker audits.
- `tests/test_skill_integrity.py`: 5 tests asserting 325 + 89 = 414 skills,
  550 workers, 20 departments, no unresolved references.

## Stage 3 — Security and governance — EXISTING / PARTIAL
- Existing: optional deployment-wide bearer auth, CORS allowlist, research-only
  execution boundary, allowlisted read-only browser tool, sandboxed Camofox
  browser design, secret-free diagnostics.
- Remaining: per-user identity/roles, rate limiting, independent security review.

## Stage 4 — Research, backtesting and market-making methodology — EXISTING / REFERENCE
- Existing: historical research modules, evidence/citation auditing, benchmark
  and promotion review, deterministic 300-skill research pack.
- Added: Freqtrade-derived backtest research skill (lookahead/recursive checks,
  walk-forward, reproducibility).
- Imported AutoHedge market-making and execution code remains inert; logs are
  available for historical replay research only.

## Stage 5 — Frontend/terminal completeness — PARTIAL
- Verified real backend connections for watchlists, research, runs, workers,
  learning, validation and coverage views.
- Remaining: no frontend unit-test framework; multi-panel layout customisation
  and some advanced visualisation milestones are still open in `docs/ROADMAP.md`.

## Stage 6 — Infrastructure and CI — EXISTING / EXTERNAL
- GitHub Actions quality workflow passes on `main`; root and project-site
  frontend builds verified locally; `npm audit` clean for production deps.
- Docker Compose and Trivy cannot be executed in this container; CI remains the
  authoritative check.

## Execution order for remaining work
1. Per-user auth/authorization and rate limiting (security gate for public use).
2. Frontend test framework and component/integration tests.
3. Licensed live/delayed market-data provider (only after legal/security review).
4. Host-specific backup/restore and observability drills.
5. Distributed queue/cloud workspaces — only if the research-only architecture
   is deliberately expanded; explicitly excluded from this delivery.
