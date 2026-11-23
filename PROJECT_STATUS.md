# PROJECT STATUS — verified 2026-11-23

Last reviewed: 2026-11-23 on branch `feat/complete-mission`, based on
`origin/main` `308e1ff066b700cfad9f8c1a408e2563ef2e0582`.

## Current state

- Audit branch head: `2bae059a` (see `git log -1 --format=%H` locally for the
  authoritative value after additional commits). Final commit SHA and CI run
  URL are recorded in `FINAL_TEST_RESULTS.md`.
- Product boundary: **research-only market intelligence**. Broker execution,
  wallet private keys, transaction signing, live order routing and market
  making are disabled by design; health reports `broker_execution: false`.
- Completion is **not** claimed: public exposure gates, expanded CI workflow,
  host drills and independent security review are unverified.

## Audit and recovery

Local `main` had diverged (56 local commits, 17 origin commits) and tracked
8,789 files including generated artifacts. It is preserved intact at
`recovery/local-main-56-commits` (`906b3765`) with source patches in
`/tmp/opencode/`. No force-push, reset, rebase, merge or discard occurred.

## Security

- Four-role per-user sessions, deployment bearer auth, deny-by-default
  sensitive-route policy, ownership checks, audit events, strict startup env
  gate, session fixation/CSRF rotation, header hardening, proxy-header
  stripping and Redis-capable rate limiting are implemented and tested.
- New in this audit: DR stale-lock fix and PR #8 ownership fencing of research
  side effects, both with regression tests.
- Verified gaps remain (role enforcement conditional on `MARKET_MIND_USER_AUTH`,
  globally visible unregistered resources, write routes without minimum role,
  Origin checks off by default, client-supplied data-status labels). See
  `SECURITY_AUDIT.md`.
- Public exposure BLOCKED pending TLS, segmentation, ingress controls and
  independent review. Runbook: `docs/PUBLIC-EXPOSURE-HARDENING.md`.

## Architecture

- Single-host SQLite queue with one supervisor. ADR-0001 (ported from PR #39)
  is design-only; PR #38's obsolete lease code was not ported.
- Market data provenance-tagged; no licensed live provider configured.
- Imported execution code inert. Single shared intelligence core, not 550
  independent models.

## Verification

| Check | Result |
| --- | --- |
| Backend suite | PASS — 1045 tests |
| Frontend node:test + Vitest | PASS — 10 + 117 tests |
| Frontend build / audits | PASS |
| pip-audit / npm audit | PASS — 0 known vulnerabilities |
| CI-equivalent Trivy scan | PASS — 0 findings at MEDIUM+ |
| Docker / host drills | BLOCKED locally; operator work |
| CI for final push | See `FINAL_TEST_RESULTS.md` for the recorded run |

## Pull requests

Open and triaged: #76 (owner workflow scope), #40 (ported here), #39 (ADR
ported here), #38 (obsolete design, not ported), #8 (fencing ported here).
No PR was merged in this audit; dispositions are documented in
`REMAINING_WORK.md`.

## Next actions (owner/operator)

1. Grant `workflow` scope, land `security/trivy-ci-scope`, then #76.
2. TLS ingress, network segmentation, ingress rate limits, independent review.
3. Host/S3/Docker/process-kill drills on an authorized host.
4. Decide on ADR-0001 implementation and data-status attestation fix.
