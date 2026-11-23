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

## Still blocked or intentionally excluded

1. **Public exposure — BLOCKED (external)**: TLS issuance/scan, network
   segmentation, ingress controls, independent penetration test and formal
   security review are operator/external work. No public deployment authorized.
2. **Trivy CI scope — BLOCKED (OAuth permission)**: the expanded job is
   committed only on local branch `security/trivy-ci-scope` (`0c89aa68`).
   Pushing `.github/workflows/*` requires the owner to run
   `gh auth refresh -h github.com -s workflow` and approve the device code.
   The main audit branch is intentionally left pushable without workflow edits.
3. **Remaining server-side security gaps — PARTIAL / documented**: all
   authorization and per-user role enforcement is conditional on
   `MARKET_MIND_USER_AUTH`; with only the shared bearer token every holder
   reaches admin routes. Unregistered resources are globally visible, several
   write routes have no minimum role, Origin checks are off by default, roles
   in live sessions are not re-read from configuration, and the in-process
   limiter ignores trusted-proxy settings. See `SECURITY_AUDIT.md`.
4. **Market-data labelling — PARTIAL**: `/api/market-data/store` accepts a
   caller-declared `status`/`source`; a synthetic batch could be labelled live.
   No provider is configured; `no_live_provider_configured` is reported.
5. **PR #38 — NOT PORTED**: its lease implementation depends on an obsolete
   supervisor architecture. Port to the current `run_supervisor` loop with
   fresh tests if supervisor leadership is approved as new work (ADR-0001).
6. **PR #76 — BLOCKED (owner)**: one-line `configure-pages@v6` bump needs the
   workflow-scope grant, then a normal authorized merge.
7. **Host operations — NOT RUN**: cron/systemd install, real S3 target, Docker
   volume restore (`docker` absent), real migration runner, host restart and
   process-kill drill. See `docs/BACKUP_RECOVERY_DRILL.md` and
   `docs/PUBLIC-EXPOSURE-HARDENING.md`.
8. **Multi-host execution — NOT IMPLEMENTED (intentional)**: SQLite single-host
   queue with one supervisor; `distributed_queue.py` is a contract only.
9. **Licensed live data — NOT CONFIGURED (intentional)**: licensing gate
   remains; no current-market-price claims are permitted.
10. **Imported execution code — INTENTIONALLY INERT**: AutoHedge, FinceptTerminal
    and Freqtrade remain reference-only; no wallet keys, signing or order routing.

## Completion boundary

No public deployment is authorized. Completion is not claimed while TLS,
network segmentation, ingress controls, independent security testing and the
expanded CI workflow remain unverified.
