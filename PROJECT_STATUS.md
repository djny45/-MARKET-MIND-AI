# PROJECT STATUS — verified 2026-11-23

Last reviewed: 2026-11-23 on branch `feat/complete-mission`, based on
`origin/main` `308e1ff066b700cfad9f8c1a408e2563ef2e0582`.

## Current state

- Integrated code commit on `main`:
  `2cdb73c60aef20b867ee2bb563728714b9571133` (merge of PR #89: security-gap
  closures, WAL-sidecar leak fix). CI for that exact SHA:
  <https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45234033798> — all five
  jobs PASS. PRs #82–#89 were reviewed, CI-green and merged by authorized
  operations; no unreviewed PR was merged. Nine real browser tests, the
  S3-compatible drill, HTTP-level session-expiry and XFF-stripping tests are
  recorded in `docs/FINAL_ACCEPTANCE_REPORT.md` and
  `docs/RECOVERY_DRILL_EVIDENCE.md`. See `docs/FINAL_ACCEPTANCE_REPORT.md` for
  the three separate acceptance statuses.
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
- Write-route roles, strict Origin enforcement, live role re-read, trusted-proxy
  limiting, Redis recovery, market-data status attestation, token redaction,
  shared-bearer viewer downgrade and SQLite-durable ownership with deny-unknown
  resources were fixed with regression tests. See `SECURITY_AUDIT.md`.
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
| Backend suite | PASS — 1,181 tests on this branch (1 skipped: no nginx binary) |
| Frontend node:test + Vitest | PASS — 10 + 127 tests |
| Frontend build / audits | PASS |
| pip-audit / npm audit | PASS — 0 known vulnerabilities |
| CI-equivalent Trivy scan | PASS — 0 findings at MEDIUM+ |
| Ingress config assertions | PASS — 12 tests (parse + `nginx -t` when available) |
| Isolated recovery drills | PASS — backup/restore/parity/retention/stale-lock and `kill -9` requeue |
| Perimeter in a real container | PASS — CI Docker job fetched `/api/ready` through nginx and ran `load_check.py` |
| Docker volume / host / S3 drills | BLOCKED locally; operator work |
| CI for final push | See `FINAL_TEST_RESULTS.md` for the recorded run |

## Pull requests

Open and triaged: none. #76 (dependabot `configure-pages` 6) was merged as
`af81ad01`; #85 (ingress limits, fail-closed skill cadence, verified recovery
drills, S3 prerequisite) was merged as `32561c1d`. #40, #39, #38 and #8 were
closed earlier with dispositions in `REMAINING_WORK.md`. The only remaining
push is `security/trivy-ci-scope`, which GitHub rejects with "refusing to allow
an OAuth App to create or update workflow ... without `workflow` scope".

## Next actions (owner/operator)

1. Grant `workflow` scope (`gh auth refresh -h github.com -s workflow`) and land
   `security/trivy-ci-scope`; this is the only push still rejected.
2. TLS ingress, network segmentation, edge verification of the shipped rate
   limits, independent review.
3. Host/S3/Docker-volume/process-kill drills on an authorized host, plus
   `npx playwright install-deps` to unlock real-browser responsive tests.
4. Decide on ADR-0001 implementation and data-status attestation fix.

## Re-verified 2026-11-24 (feature branch)

Items 1 and the browser-test part of item 3 above are **stale**: the expanded
Trivy job and the Playwright job are in `.github/workflows/quality.yml` on
`main`, and CI run `45268550062` on `1a13bfe2` passed all six jobs.

`fix/close-remaining-verification-gaps` re-verified the current tree and closed
all locally executable gaps: backup freshness reporting, S3-compatible transfer
with a stdlib fake-S3 integration test, an operator Docker-volume drill with a
fake-Docker test, DR secret redaction, eight confirmed auth/rate-limit/audit
defects, dual-auth browser integration, and offline preflight/ingress guards.
See `REMAINING_WORK.md` § "Re-verification 2026-11-24" for the exact evidence and
the updated 32/40 acceptance-inventory counts (previously 27/31). Private
verification remains **7/10**; public deployment remains **0/6**. Real cloud S3,
real Docker volumes and host service/restart drills are still operator work.

Phase 2 on `fix/phase2-acceptance-gaps` (code through `d9169e81`) closed the five
partial checks with local evidence, added host-schedule and config-preflight
scaffolding, and corrected the unsupported 28/28 feature claim to 26/26.
Acceptance inventory is now **37/40 verified, 0 partial, 3 BLOCKED**. The three
external gates have procedures in
`docs/EXTERNAL-VERIFICATION-CHECKLIST.md`; private verification stays 7/10 and
public deployment 0/6.

Continuous Phase 4 (PR #105) fixed supervisor lease acquisition/renewal, Redis
limiter transitions, and login CSRF compatibility with regression tests, and
added failing-closed container image scanning. The frontend image is clean after
pinning nginx 1.31.7; the backend image still has OS-level CVEs with no fixed
version, so the container gate remains **FAIL** and PR #105 must not be merged.
See `docs/CONTAINER-SCAN-FINDINGS.md` and
`docs/MULTI-HOST-ARCHITECTURE-ASSESSMENT.md`.
