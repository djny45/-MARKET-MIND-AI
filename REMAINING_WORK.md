# REMAINING WORK — evidence-based (2026-11-23)

This repository-level audit started from `origin/main` commit
`308e1ff066b700cfad9f8c1a408e2563ef2e0582` on branch `feat/complete-mission`.
Nothing here is claimed as delivered without a recorded command/result.

## Recovered local work

Local `main` (`906b3765e3af03a866f8dd84daa7edf74f71fbc3`) had diverged: 56
commits not on `origin/main`, 17 commits on origin not on local. Local `main`
also had **no `.gitignore`** and tracked 8,789 files, including 7,569
`node_modules` paths, 5,855 `frontend/dist` paths and 298 `.pyc` files.
`origin/main` tracks 910 files with generated paths ignored.

The entire local line is preserved without rewriting history at
`recovery/local-main-56-commits`. Text patches of unique source/doc files are
at `/tmp/opencode/recovery-added-source.patch` and
`/tmp/opencode/recovery-modified-source.patch` (data binaries/logs excluded).
Useful unique work already ported to this branch: `AuthPanel.tsx`, TLS ingress
example, ADR-0001. No force-push, reset, rebase, merge or discard was performed.

## Completed in this audit

- Fixed `DrLock.stale_count()` reading only its own lock file; added a
  regression test that keeps live locks of other DR processes intact.
- Ported PR #8 ownership fencing: quality evaluation is now written inside the
  fenced completion transaction and learning memory only after a successful
  fenced finalization. Added the stale-executor regression test.
- Added a frontend authentication UI (login/logout, session status, expired
  state, role-aware navigation, accessible errors), an observation screener,
  a coverage heatmap, a working Help dialog, `loadNews` HTTP failure handling
  and watchlist busy/error states.
- Ported PR #39 ADR and PR #40 screener/heatmap functionality.
- Added `docs/PUBLIC-EXPOSURE-HARDENING.md` and a TLS ingress example.
- Closed server-side gaps: analyst minimum role on four write routes, strict-mode
  Origin enforcement, live role re-read with removed-user revocation,
  trusted-proxy-aware in-process limiter, Redis recovery after cooldown,
  server-attested market-data status/source, and token redaction under benign
  keys. All have regression tests.
- Ported PR #38's lease-loss guarantee to the current `run_supervisor` loop:
  CAS lease renewal and dispatch revalidation, with three regression tests.
  SQLite remains single-host; no broker was introduced.
- Added explicit access-denied state for role-gated frontend navigation.
- Implemented the seven previously missing frontend modules (portfolio analytics,
  risk analytics, system health, provider health, audit events, backup status
  and settings), each connected to a real backend endpoint with role gating and
  loading/error states. Added `GET /api/backup/status` (admin-only) and 6 UI tests.
- PR dispositions recorded on GitHub: #8, #39, #40 closed as ported; #38 closed
  as obsolete architecture; #76 left open with an owner-action comment.

## Newly executed recovery evidence (2026-11-23)

- Real isolated backup → checksum → clean restore → integrity/row-count parity,
  retention pruning and stale-lock recovery drill: PASS. Transcript and commands:
  `docs/RECOVERY_DRILL_EVIDENCE.md` §1.
- Real process-kill (`kill -9`) recovery drill in an isolated DB: PASS — the
  killed executor's `running` task was requeued exactly once without dispatch.
  Evidence: `docs/RECOVERY_DRILL_EVIDENCE.md` §2.
- Added stdlib S3-compatible upload/download prerequisite
  (`scripts/s3_offhost.py`) with env-only credentials, dry-run and secret-free
  output; tests PASS. No real S3 target was configured or tested.
- Ingress perimeter limits (nginx `limit_req`, `limit_conn`, CSP, 429) were
  preserved from in-progress work and validated by 11 config tests (1 nginx-binary
  test correctly skipped).

## Still blocked or intentionally excluded

1. **Public exposure — BLOCKED (external)**: TLS issuance/scan, network
   segmentation, ingress controls, independent penetration test and formal
   security review are operator/external work. No public deployment authorized.
2. **Trivy CI scope — BLOCKED (OAuth permission)**: the expanded job is
   committed only on local branch `security/trivy-ci-scope` (`0c89aa68`).
   Pushing `.github/workflows/*` requires the owner to run
   `gh auth refresh -h github.com -s workflow` and approve the device code.
   The main audit branch is intentionally left pushable without workflow edits.
3. **Resolved: shared bearer and ownership.** Bearer-only callers are downgraded
   to viewer for sensitive routes; ownership is SQLite-durable and unknown
   resource references are denied. Local mode with both auth flags off remains
   intentionally open for research; operator deployments must enable auth.
4. **Market-data labelling — RESOLVED at the API boundary**: live/delayed claims
   now require an operator-attested source; no provider is configured and
   `no_live_provider_configured` is reported. Cryptographic provider attestation
   remains out of scope until a real licensed provider is added.
5. **PR #38 — CLOSED as obsolete**: its lease implementation targeted a removed
   supervisor architecture. The guarantee was ported to `run_supervisor`; full
   multi-supervisor contention tests remain gated by ADR-0001.
6. **PR #76 — BLOCKED (owner)**: one-line `configure-pages@v6` bump needs the
   workflow-scope grant, then a normal authorized merge.
7. **Host operations — PARTIAL**: isolated backup/restore, retention, stale-lock
   and process-kill recovery drills are now executed with evidence. Still NOT
   RUN: cron/systemd install, real S3 upload/restore, Docker volume restore
   (`docker` absent), host service restart and real migration runner. See
   `docs/RECOVERY_DRILL_EVIDENCE.md` and `docs/PUBLIC-EXPOSURE-HARDENING.md`.
8. **Multi-host execution — NOT IMPLEMENTED (intentional)**: SQLite single-host
   queue with one supervisor; `distributed_queue.py` is a contract only.
9. **Licensed live data — NOT CONFIGURED (intentional)**: licensing gate
   remains; no current-market-price claims are permitted.
10. **Imported execution code — INTENTIONALLY INERT**: AutoHedge, FinceptTerminal
    and Freqtrade remain reference-only; no wallet keys, signing or order routing.

## Integration state

All completed work was merged into `main` at
`7f99013955a5e60dbe6f1ee292ad0d2d722fd122` via reviewed PR #84 (after PRs
#82 and #83). CI on that exact SHA passed all five jobs
(<https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45207137712>).
The old divergent local `main` (`906b3765`) and all recovery branches remain
untouched.

1. **Real-browser responsive tests — NOT RUN**: no browser runner is configured;
   jsdom checks media-query declarations and DOM availability only.

## Completion boundary

No public deployment is authorized. **100% is not claimed**: TLS, network
segmentation, ingress controls, independent security testing, the expanded Trivy
CI job (owner workflow scope), real S3/Docker/host drills, cryptographic data
provider attestation and durable cross-worker ownership remain unverified or
externally blocked, with exact owner actions documented above.
