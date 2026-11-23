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
- PR dispositions recorded on GitHub: #8, #39, #40 closed as ported; #38 closed
  as obsolete architecture; #76 left open with an owner-action comment.

## Still blocked or intentionally excluded

1. **Public exposure — BLOCKED (external)**: TLS issuance/scan, network
   segmentation, ingress controls, independent penetration test and formal
   security review are operator/external work. No public deployment authorized.
2. **Trivy CI scope — BLOCKED (OAuth permission)**: the expanded job is
   committed only on local branch `security/trivy-ci-scope` (`0c89aa68`).
   Pushing `.github/workflows/*` requires the owner to run
   `gh auth refresh -h github.com -s workflow` and approve the device code.
   The main audit branch is intentionally left pushable without workflow edits.
3. **Remaining server-side gaps — PARTIAL**: role and ownership enforcement
   remains conditional on `MARKET_MIND_USER_AUTH`; a shared bearer-token-only
   deployment still grants every holder admin routes. `OwnershipRegistry` is
   in-memory and unregistered refs are globally visible. These require an auth
   model redesign and a durable ownership store, not a one-line change.
4. **Market-data labelling — RESOLVED at the API boundary**: live/delayed claims
   now require an operator-attested source; no provider is configured and
   `no_live_provider_configured` is reported. Cryptographic provider attestation
   remains out of scope until a real licensed provider is added.
5. **PR #38 — CLOSED as obsolete**: its lease implementation targeted a removed
   supervisor architecture. The guarantee was ported to `run_supervisor`; full
   multi-supervisor contention tests remain gated by ADR-0001.
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

## Integration state

All completed work was merged into `main` at
`e8d9f3284de182549d72079101ac67a0bef582c0` via reviewed PR #82. CI on that exact
SHA passed all five jobs (<https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45184633962>).
The old divergent local `main` (`906b3765`) and all recovery branches remain
untouched.

## Completion boundary

No public deployment is authorized. **100% is not claimed**: TLS, network
segmentation, ingress controls, independent security testing, the expanded Trivy
CI job (owner workflow scope), real S3/Docker/host drills, cryptographic data
provider attestation and durable cross-worker ownership remain unverified or
externally blocked, with exact owner actions documented above.
