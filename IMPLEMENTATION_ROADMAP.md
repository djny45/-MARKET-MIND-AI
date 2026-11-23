# IMPLEMENTATION ROADMAP — verified status (2026-11-23)

Status values: **DONE** (verified by command in this audit), **PARTIAL**,
**BLOCKED** (permission/host action), **NOT IMPLEMENTED** (intentional scope).
Baseline: `origin/main` `308e1ff0`; audit branch `feat/complete-mission`.

## Stage 0 — Repository audit — DONE

Divergence analysed: local `main` 56 commits ahead / 17 behind, with 8,789
tracked files versus 910 on origin. Entire local line preserved in
`recovery/local-main-56-commits`; unique source patches saved under
`/tmp/opencode/`. No force-push, reset, rebase, merge or discard.

## Stage 1 — Security hardening — PARTIAL

Four-role authorization, ownership registry, audit events, strict env gate,
session/CSRF rotation, proxy-header stripping and Redis-capable rate limiting
exist and are tested. In this audit: fixed DR stale-lock handling, ported PR #8
ownership fencing, then closed write-route roles, strict Origin, stale roles,
trusted-proxy limiting, Redis recovery, market-data attestation and audit
redaction, each with regression tests. PR #38's lease-loss guarantee was ported
to the current supervisor. Remaining architectural gaps (shared bearer role
separation, durable ownership store) are in `SECURITY_AUDIT.md`; public exposure
remains BLOCKED.

## Stage 2 — Frontend — DONE for the requested gaps

Added authentication UI (login/logout, session status, expired state,
role-aware navigation, accessible errors), observation screener, coverage
heatmap, Help dialog, `loadNews` HTTP failure handling and watchlist
busy/error states. 10 node:test + 117 Vitest tests pass; production build and
`npm audit --omit=dev` clean. Real-browser responsive verification remains
BLOCKED (no browser test runner configured). See `docs/FRONTEND_TESTING.md`.

## Stage 3 — Backup and recovery — PARTIAL

Backup integrity, SHA-256 sidecars, retention, generic off-host hook, clean
restore, parity checks, resume, stale-lock recovery, armed rollback, webhook
alerts and cron/systemd generation are implemented and unit-tested. Host cron
install, Docker volume restore, real S3, real migration runner and process-kill
drill are operator-only and NOT RUN. See `docs/BACKUP_RECOVERY_DRILL.md` and
`docs/PUBLIC-EXPOSURE-HARDENING.md`.

## Stage 4 — Trivy and security CI — PARTIAL / BLOCKED

Local scan: `trivy fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL`
clean after excluding local-only `third_party/` and `.venvs/`. Expanded CI job
(vuln+misconfig+secret, MEDIUM+, config scan, fail-closed) is committed on
`security/trivy-ci-scope`; pushing it requires owner
`gh auth refresh -h github.com -s workflow`. `docs/TRIVY_CI_AUDIT.md` corrected.

## Stage 5 — PR reconciliation — DONE with dispositions

#8, #39 and #40 closed on GitHub as ported; #38 closed as obsolete architecture
with its guarantee reimplemented in the current supervisor; #76 remains open
with a documented owner workflow-scope action. No PR was merged unreviewed.

## Stage 6 — Market data and queue scope — DONE (design boundary kept)

ADR-0001 ported: SQLite remains single-host, one supervisor; no broker.
Licensing gate preserved; no live provider configured; imported execution code
inert. Data-store labelling gap documented in SECURITY_AUDIT.md.

## Stage 7 — Dependency and supply-chain audit — DONE

`pip-audit -r backend/requirements.txt`: no known vulnerabilities.
`npm audit`: 0 advisories; lockfile consistent with `package.json` (19/19
ranges, integrity hashes present). Actions are tag-pinned (not SHA-pinned) and
`npm install` is used in CI instead of `npm ci` — recorded as hardening
opportunities, not silent defects. `compileall` clean.

## Stage 8 — Documentation — DONE

All eight mandated reports rewritten against current code and recorded
commands; stale claims (untracked lockfile, missing USER 101, absent ADR
branch) corrected.

## Remaining execution order (owner/operator)

1. Grant workflow scope and land `security/trivy-ci-scope`, then #76.
2. Provision TLS ingress, segmentation, ingress rate limits and independent
   security review before any public exposure.
3. Decide whether to fund ADR-0001 supervisor-lease implementation (PR #38
   port) and the market-data labelling attestation fix.
