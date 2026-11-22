# IMPLEMENTATION ROADMAP — verified status (2026-11-22)

Status values: **DONE** (verified locally and/or in CI), **PARTIAL**, **BLOCKED**
(external permission/host action), **NOT IMPLEMENTED** (intentional scope).

## Stage 0 — Baseline audit — DONE
Fresh inspection of latest `main` (`89c20dde`) replaced stale completion
claims. Baseline: 987 backend tests, 10 frontend tests, build green after
installing declared dependencies.

## Stage 1 — Security and authorization — DONE (public exposure BLOCKED)
Four-role authorization with resource ownership checks, strict startup env
gate, session fixation/CSRF rotation, hardened cookies/headers/proxy handling,
Redis-capable distributed rate limiting with safe fallback, and audit-event
aggregation. Tests: 35 focused + full suite. Details: `SECURITY_IMPLEMENTATION.md`.

## Stage 2 — Frontend component testing — PARTIAL
Vitest + jsdom + Testing Library + jest-axe suite: 99 UI tests over real
components, API mocks, loading/error states, keyboard/role checks. Original
10 node:test tests still pass. Gaps: no auth UI, screener or heatmap exists on
`main`; computed responsive layout needs a real browser.
Details: `docs/FRONTEND_TESTING.md`.

## Stage 3 — Backup and disaster recovery — DONE (host actions NOT RUN)
Journaled/resumable backups, configurable retention, off-host hook, SHA-256
integrity, clean restore, migration rollback, interrupted-task and restart
recovery, incident webhook (redacted), cron/systemd generators. Executed local
drills with verbatim evidence in `docs/BACKUP_RECOVERY_DRILL.md`.

## Stage 4 — Trivy and security CI — PARTIAL / BLOCKED
Trivy 0.76.2 installed locally; filesystem scan with vuln+misconfig+secret at
MEDIUM/HIGH/CRITICAL is clean after the `USER 101` Dockerfile fix. CI job still
uses the narrower scope; workflow edits are blocked by missing OAuth
`workflow` scope. Details: `docs/TRIVY_CI_AUDIT.md`.

## Stage 5 — Dependabot and PR cleanup — DONE (one PR BLOCKED)
Reviewed all 19 open PRs. Merged #5, #6, #7, #9, #75; closed 9 obsolete,
duplicate or incompatible PRs. #77 closed for proven ERESOLVE incompatibility.
#76 remains open only because of the OAuth scope blocker.

## Stage 6 — Market data and queue scope — DONE
ADRs recorded: single-host SQLite queue, provenance-gated market data, inert
execution code, esbuild frontend tests. `provider_health.py` adds freshness and
health reporting without activating any provider.

## Stage 7 — Final verification — DONE (Docker checks BLOCKED locally)
1043 backend tests, 109 frontend tests, builds, audits, Trivy and DR drills
all passed locally. Docker absent → Compose validation remains CI-authoritative.

## Stage 8 — Documentation — DONE
All final reports rewritten with actual commands, results, commit hashes and
blockers; stale claims (old commit SHA, old PR count, old test counts) removed.

## Remaining execution order
1. Owner grants `workflow` scope (`gh auth refresh -h github.com -s workflow`),
   then merge #76 and update the Trivy CI job scope.
2. Owner provisions TLS ingress, network segmentation and independent review
   before any public exposure.
3. Revive #40 as a fresh PR if screener/heatmap UI is approved product scope.
4. Redesign #38 lease-loss protection for the current supervisor heartbeat.
5. Multi-host queue and licensed live data only via new ADRs and legal review.
