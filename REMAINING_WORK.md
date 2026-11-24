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
6. **PR #76 — MERGED**: the one-line `actions/configure-pages` 5 → 6 bump
   landed on `main` as merge commit `af81ad01` after all five CI jobs and the
   Vercel preview check passed. Merging a workflow PR does not need the
   `workflow` scope; only *pushing* workflow files does.
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
`2cdb73c60aef20b867ee2bb563728714b9571133` via reviewed PR #89 (after PRs
#82–#88). CI on that exact SHA passed all five jobs
(<https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45234033798>).

The Docker Compose job in that run built the frontend image with the new
`nginx-limits.conf`, started the stack, and fetched `/api/ready` through the
rate-limited perimeter before running `scripts/load_check.py` (120 requests,
concurrency 8), so the perimeter configuration is exercised in a container even
though no local `nginx` binary exists.
The old divergent local `main` (`906b3765`) and all recovery branches remain
untouched.

1. **Real-browser responsive tests — RESOLVED locally (2026-11-24)**: Chromium is
   downloaded and present in `~/.cache/ms-playwright`, but it could not launch in
   this container because `libnss3`, `libnspr4`, `libxcomposite1`, `libxdamage1`
   and `libxrandr` were missing and there is no root to install them.
   Workaround proven on the Phase 6 tree: the NSS libraries are present in
   `~/.cache/camoufox`, and `xorg-libxcomposite`, `xorg-libxdamage`,
   `xorg-libxrandr` and `at-spi2-atk` install into an unprivileged conda prefix.
   With
   `LD_LIBRARY_PATH=/tmp/opencode/pwlibs/lib:$HOME/.cache/camoufox:$LD_LIBRARY_PATH`
   and Node 22.23.5, `npx playwright test` passes **9/9** locally, matching CI.
   This removes a previously recorded local-only blocker; it changes no
   production code and grants no new capability.

## Completion boundary

No public deployment is authorized. **100% is not claimed**: TLS, network
segmentation, ingress controls, independent security testing, the expanded Trivy
CI job (owner workflow scope), real S3/Docker/host drills, cryptographic data
provider attestation and durable cross-worker ownership remain unverified or
externally blocked, with exact owner actions documented above.

---

## Re-audit 2026-11-23 (current state — appended, historical results above unchanged)

Tested commit: `ecca456eacd8358f7cae9aa97ef5788759100d0d` (= `origin/main`, clean tree).
Environment: Linux container, Python 3.11.6, Node 22.23.5 via nvm, uid 1000 with
`no_new_privileges` (no sudo), `docker`/`docker compose` binaries absent, no
`systemctl`/`crontab`, no `MARKET_MIND_S3_*` variables set (presence checked only;
no values printed). Research-only boundary unchanged and verified.

### Status-document reconciliation

The previous report published **8/10 (80%)** for private verification while
listing **three** remaining infrastructure gates, and in the same document also
published **7/10 (70%)**. That checklist is defective: it bundled the three
infrastructure drills into two items and counted the local moto S3 compatibility
check as if it were a real cloud restore. The original 8/10 result is preserved
above; the corrected, non-overlapping matrix below keeps the denominator at 10
and counts only PASS as complete.

### Verification matrix (corrected — 10 unique gates)

Check|Required evidence|Status|Evidence location|Blocker
---|---|---|---|---
Backend tests + Python compilation | 1122 tests OK (1 skipped), compileall exit 0 | PASS | `/tmp/opencode/audit2-backend.log`; compile exit captured in audit transcript | none
Frontend tests + production build/typecheck | 10 node:test, 123 Vitest, tsc + esbuild build OK | PASS | `/tmp/opencode/audit2-node.log`, `audit2-vitest.log`, `audit2-build.log`, `audit2-typecheck.log` | none
Real-browser responsive tests | 9/9 desktop/tablet/mobile locally and in CI | PASS | `/tmp/opencode/audit2-browser.log`; CI run 45252956328 | none
Dependency and vulnerability audits | pip-audit and npm audit 0 advisories; Trivy `vuln,misconfig,secret` MEDIUM+ filesystem and config scan in CI | PASS | `/tmp/opencode/audit2-pip-audit.log`, `audit2-npm-audit.json`, `audit2-trivy-fs.log`; CI run 45252956328 (PR #92 merged) | none
Recovery drills (database + process kill) | backup/SHA-256/clean restore/matched parity, retention 2/4, stale lock removed; kill -9 requeued 1 task with 0 still running | PASS | `/tmp/opencode/audit2-dr.log`, `/tmp/opencode/audit2-kill.log`; 63 targeted tests in audit transcript | none
Migration rollback and live readiness probes | armed→rolled_back with sha256 match; `/api/health` 200, `/api/ready` 200 with writable DB and storage ok | PASS | `/tmp/opencode/audit2-migration`; live probe transcript in audit log | none
Docker Compose integration and health | Compose job builds stack and probes `/api/ready` in CI | PASS | CI run 45255622609 on final merged commit | none
Docker named-volume backup/restore | isolated volume backup, checksum, restore into separate volume, data integrity | BLOCKED | no evidence — not executed | `docker` and `docker compose` binaries absent on this host; requires a Docker-capable private host and operator authorization
Real cloud S3 restore | real endpoint upload/download, SHA-256 parity, restore into isolated location, DB integrity | BLOCKED | local moto compatibility drill only (`/tmp/opencode/audit2-s3` parity PASS) | no `MARKET_MIND_S3_*` endpoint, bucket or credentials set; requires operator-provided authorized target
Host systemd/cron restart recovery | inspect service/timer config, controlled restart, verify health, integrity and task recovery | BLOCKED | no evidence — not executed | uid 1000 with `no_new_privileges`, no sudo, no `systemctl`/`crontab`; requires operator host access and explicit authorization

Corrected private-verification score: **7/10 PASS (70%)** — 7 PASS, 0 FAIL, 3 BLOCKED.
The local moto S3 drill is a prerequisite, not a real infrastructure drill; the
migration rollback and readiness/headroom probes are local evidence and are not
substituted for host-level gates.

### Commands and outcomes (all executed on `ecca456e`)

- `python -m compileall -q backend/app scripts` → exit 0.
- `PYTHONPATH=.:./backend /tmp/opencode/backend-venv/bin/python -m unittest discover -s backend/tests -q` → 1122 OK, 1 skipped, exit 0.
- `npm test` → 10/10; `npm run test:ui` → 123/123; `npm run build` and `npm run typecheck:test` → exit 0 (Node 22.23.5).
- `LD_LIBRARY_PATH=/tmp/opencode/browser-root/usr/lib/x86_64-linux-gnu npx playwright test` → 9 passed, exit 0 (library-only workaround; no host init changes).
- `pip-audit -r backend/requirements.txt` → no known vulnerabilities; `npm audit --omit=dev` → 0 vulnerabilities.
- `trivy fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL --skip-dirs third_party --skip-dirs .venvs .` → exit 0, 0 findings.
- Targeted `unittest` across backup/WAL hygiene, recovery drills, session middleware, authorization, service status, CI workflow config and S3 adapter → 63 OK.
- `run_dr_final.sh` → status matched, integrity ok, parity match, retention kept 2, stale lock removed (exit 0).
- `run_process_kill_drill.sh` → requeued 1, still_running 0 (exit 0).
- `migration_rollback.py prepare → rollback → status` → status rolled_back, sha256 match, post-rollback integrity ok.
- Local moto S3 upload/download → HTTP 200/200, SHA-256 + byte parity, `credentials_exposed=false` (simulation only).
- Live `/api/health` and `/api/ready` → 200/200; ready reports `writable: true` and storage `ok`; bounded load probe 60 requests, error rate 0, p95 8.89 ms.
- `docker compose config` → NOT RUN (binary absent). CI Compose job is PASS (local execution not claimed).

Local `trivy config .` additionally reports DS-0002 (HIGH) and DS-0026 (LOW)
inside untracked, git-excluded `third_party/` reference trees. These are not in a
clean CI checkout, do not affect the scanned tree, and are deliberately left
untouched as inert reference material.

### Remaining public deployment requirements

Public deployment remains **NOT READY (0/6)**: TLS issuance and scan, network
segmentation, ingress hardening, independent penetration testing, formal security
review, and production-scale recovery evidence. All are external operator work;
no public ingress was enabled by this audit.

### Completion scores (this audit)

- Application features: **26/26 (100%)** — `docs/acceptance-inventory.json` module inventory; full local suites pass.
- Private research-platform verification: **7/10 (70%)** — corrected matrix above; three infrastructure gates BLOCKED.
- Public deployment readiness: **0/6 (0%)** — no independent external evidence exists.

---

## Re-verification 2026-11-24 — closing locally executable work

Baseline: `main` `1a13bfe28974ebdf2877ba0180889122aeafd7e0` (clean; all six CI
jobs PASS in run `45268550062`). Work was done on
`fix/close-remaining-verification-gaps`; code commits `3dab5955` through
`b07c1d90`. Raw logs: `/tmp/opencode/audit4-20261124/`.

**Recalculated status:** private-platform verification is **still 7/10 (70%)**,
because all three remaining gates in the 10-gate matrix are external. Application
features remain **26/26**; public deployment remains **0/6**. The separate
acceptance inventory was corrected from 27/31 verified (README previously said
28/31) to **32/40 verified, 5 partial, 3 blocked** after adding explicit items
for locally verified work and the three external gates.

### Closed with reproducible local evidence

| Item | Evidence (this branch) |
| --- | --- |
| Backup freshness never reported a stopped schedule | `GET /api/backup/status` reports `never_run`/`ok`/`stale`, newest age and validated threshold; `test_backup_freshness.py` (7 tests) |
| S3-compatible transfer/integrity | Stdlib fake-S3 HTTP server verifies SigV4 signatures, SHA-256 parity, bad-secret rejection and fail-closed downloads; `test_s3_offhost_integration.py` (3) + `test_s3_offhost.py` (2) |
| Docker named-volume drill | `scripts/docker_volume_drill.py`: read-only `plan`, explicit `--apply`, separate target volume, no `down -v`; `test_docker_volume_drill.py` (4) with a fake Docker shim |
| DR secret leakage | Hook output, manifests and webhook reasons redacted; `test_dr_secret_hygiene.py` (3) |
| Confirmed security defects | Malformed Origin 500, unaudited rate limits, login actor field, lockout/rate-bucket eviction, identity-row growth, middleware ordering, dual-auth UI; `test_security_defect_regressions.py` (8), `test_frontend_auth_integration.py` (1), `tests/ui/api-client.test.ts` (4) |
| Offline preflight/ingress | `test_load_check.py` (3), `test_dr_environment_validation.py` (3), TLS forwarded-proto and Compose segmentation guards in `test_ingress_config.py` (14 total, 1 skip) |
| Documentation accuracy | Corrected 20×28 arithmetic, 325 vs 300+ skills, nonexistent vendored library, stale test filename, literal escapes and duplicate headings |

### Still BLOCKED (external; no evidence invented)

1. Real cloud S3 restore — no endpoint/bucket/credentials; the local fake-S3 test is a prerequisite only.
2. Docker named-volume restore on a real host — no Docker binary here; the fake-Docker test verifies the command contract only.
3. Host systemd/cron install, controlled restart and real process-kill drill — no privileges or host init access.

Public deployment remains **0/6** (TLS issuance/scan, segmentation, ingress hardening,
independent penetration test, formal review, production-scale recovery evidence).

---

## Phase 2 — closing the five partial checks (2026-11-24)

Work branch `fix/phase2-acceptance-gaps`, based on the still-open PR #100 head
`2f3db51d`. Code-complete at `d9169e81`. Every item below has executed local
evidence; **no external check was converted to PASS**.

| Check (ID) | Precise missing evidence | Closed with |
| --- | --- | --- |
| ACC-016 Worker memory isolation | Durable ownership and cross-user denial evidence | `test_worker_memory_ownership.py` (3); authorization.py docstring corrected |
| ACC-019 Market-data provenance | Cross-module provenance, stale and failure evidence | `test_research_provenance_verification.py` (6) |
| ACC-021 Local backup/restore | Aggregated recovery artifact evidence | `scripts/recovery_report.py` + `test_recovery_report.py` (6) using real local artifacts |
| ACC-025 S3 adapter contract | Orchestrator→S3→download parity evidence | `test_s3_offhost_integration.py` (4, fake S3; mock-based contract test) |
| ACC-026 Docker volume drill | Failure/cleanup/checksum contract coverage | `test_docker_volume_drill.py` (7, fake Docker shim; mock-based contract tests) |

Additional reliability scaffolding: `scripts/install_schedule.py` (5 tests),
`scripts/config_preflight.py` (4 tests), backup disk-space preflight with 3 tests,
and documentation-drift guards (`test_research_inventory_claims.py`, 3 tests).
Fake S3 and fake Docker tests are explicitly labeled mock contract tests; they
are **not** infrastructure validation.

### Corrections made during baseline revalidation

- The supplied baseline "application features 28/28" is unsupported by the
  repository inventory, which documents **26/26** modules. The acceptance
  inventory now records the correction instead of silently repeating it.
- Duplicate/overlapping rows ("Backup freshness monitoring", "Throttling audit
  and flood hardening") were folded into their parent checks and replaced by
  the distinct host-schedule and preflight checks. IDs `ACC-001`–`ACC-033` plus
  `OPS-001`–`OPS-007` are now stable and unique.
- The former three blocked rows were redefined to the externally verifiable
  checks EXT-01/02/03; the real Docker volume run is a sub-drill of EXT-02
  rather than a separately counted gap.

**Result: 37/40 verified, 0 partial, 3 BLOCKED.** Private-platform verification
remains **7/10 (70%)** and public deployment **0/6 (0%)** because the three
BLOCKED checks require external infrastructure or independent review. External
procedures, evidence requirements, rollback and responsible operators are in
[`docs/EXTERNAL-VERIFICATION-CHECKLIST.md`](docs/EXTERNAL-VERIFICATION-CHECKLIST.md).

Final local validation on this branch: backend `unittest discover -s backend/tests -q`
→ **1,260 OK, 1 skipped**; frontend `npm test` **10/10**, `npm run test:ui`
**127/127** (21 files), `npm run build` and `npm run typecheck:test` exit 0.
Raw logs: `/tmp/opencode/phase2-final/`. CI results for the pushed PR head are
recorded in the PR and final report.

---

## Phase 3 — external verification preparation (2026-11-24)

Branch `feature/phase3-external-prep`, stacked on PR #102. No external access,
credentials, privileged operations or independent approval were used.

- **PR #102 audit:** all 8 commits and 21 files reviewed. CI on head
  `e69530045225afd1f0d25ed3c97e3d12ed8019d1` (run `45353077146`) passed all six
  jobs. Automated reviewers reported 33 findings; genuine ones were fixed in the
  `fix(audit)` commit: active `EnvironmentFile=` directives, boot activation for
  the restart unit, calendar timer, symlink-safe writes, broader protected paths,
  Compose host-network/privilege/new-port checks, applied ingress-limit checks,
  recovery evidence pairing/state-dir/artifact validation, in-container volume
  fingerprint parity, GET signature verification in fake S3, and corrected
  external commands.
- **ACC-029:** `docs/S3-VERIFICATION-PACKAGE.md` documents supported providers,
  limits, encryption/checksum/metadata requirements and the real-cloud procedure.
  DR config validation now rejects partial S3 settings, invalid bucket/region and
  prefix traversal (tests added).
- **ACC-030:** `docs/HOST-RECOVERY-PROCEDURE.md` plus `host_recovery_plan.py` give
  a read-only runbook generator, systemd/cron install guidance, short-threshold
  restart drill, Docker named-volume commands, preflight and rollback. The volume
  drill now verifies fingerprints inside the target before cleanup.
- **ACC-031:** `docs/SECURITY-REVIEW-PACKAGE.md` contains the threat model,
  architecture references, dependency inventory, CI scan results, control
  evidence and penetration-test scope/evidence checklist.
- **Final audit:** `docs/FINAL-ENGINEERING-AUDIT.md` records architecture,
  database/recovery, 550-worker/325-skill registry verification, provenance and
  research-only boundary evidence.

Acceptance remains **37/40 verified, 0 partial, 3 BLOCKED**. Private-platform
verification stays 7/10 and public deployment 0/6; the three blocked checks are
external by definition.

Final Phase 3 local validation: backend `unittest discover -s backend/tests -q`
→ **1,260 OK, 1 skipped**; frontend `npm test` **10/10**, `npm run test:ui`
**127/127** (21 files), `npm run build` and `npm run typecheck:test` exit 0.
Logs: `/tmp/opencode/phase3-final/`.

---

## Final risk-reduction cycle (2026-11-24)

Branch `feature/final-risks`, stacked on PR #104. Fixed four priority risks with
regression tests:

- **Supervisor lease:** conditional acquisition, fenced heartbeats/release,
  expired-renewal rejection and renewal during long dispatch; acquisition and
  long-dispatch/concurrency tests added. Single-host only; multi-host remains a
  proposal (`docs/MULTI-HOST-ARCHITECTURE-ASSESSMENT.md`).
- **Redis cooldown:** the Redis-success path now mirrors the local window, so a
  backend transition cannot grant a second full budget; transition and
  concurrency tests added.
- **Login CSRF:** login requires `application/json` and rejects explicitly
  cross-site `Origin`; API clients without Origin and all session transitions
  remain supported; login/logout/expiry/invalid-token tests added.
- **Container scanning:** CI builds both images and runs failing-closed Trivy
  image scans with SARIF artifacts. The first real scan found 53 HIGH / 81
  MEDIUM base-image findings with mostly no fixed versions; `pip` was upgraded
  to a fixed release and findings are documented in
  `docs/CONTAINER-SCAN-FINDINGS.md`. The gate remains **FAIL** — no suppression.

Acceptance remains **37/40 PASS, 0 PARTIAL, 0 FAIL, 3 BLOCKED**. Private
verification 7/10; public deployment 0/6. Local validation after all fixes:
backend **1,260 OK, 1 skipped**; frontend **10/10**, **127/127**, clean
build/typecheck. Logs: `/tmp/opencode/risks-final2/`.

---

## Final completion cycle (2026-11-24)

Branch `feature/final-completion`, stacked on PR #103. All three earlier PRs
(#100/#102/#103) were reviewed end-to-end: no merge conflicts, no weakened
tests, all six required jobs PASS on their exact head SHAs. Findings and
dispositions are in `docs/PR-REVIEW-REPORT.md`.

Confirmed defects fixed with regressions in this cycle: failed-upload resume
finalization, migration-rollback WAL sidecars, login-lock saturation bypass,
protocol-relative CSRF token leak, unpaired recovery evidence and non-failing
CLI, content-level DB fingerprints with FK checks and unified Docker snippet,
restore overwrite rollback with failed reports, S3 config enforcement plus
bounded retries/atomic digest-checked downloads/response metadata, host-tooling
preflight, cron/calendar validation, IPv6 loopback bindings, cross-origin API
fallback and stale "550+" wording, and provider-health clock consistency.

Acceptance is unchanged at **37/40 PASS, 0 PARTIAL, 0 FAIL, 3 BLOCKED**. The
three BLOCKED checks remain external (EXT-01 real cloud S3 restore, EXT-02 real
host/Docker recovery, EXT-03 independent security sign-off). Final local
validation: backend **1,260 OK, 1 skipped**; frontend **10/10** and **127/127**
with clean build/typecheck; logs `/tmp/opencode/final-run/`.

---

## Phase 5 final risk resolution (2026-11-24)

Branch `feature/phase5-risk-resolution`, stacked on PR #105.

- **Two-process supervisor race:** added an isolated test with two real
  processes contending for the SQLite lease. Exactly one acquires leadership,
  recovers and dispatches the single task; the loser has no side effects; the
  winner releases the lease. ADR-0001 and the multi-host assessment now state
  that this closes the single-host race check only, not distributed execution.
- **Container investigation:** evaluated `python:3.12-slim-bookworm` in CI; it
  was substantially worse (109 HIGH / 152 MEDIUM) than the current Debian 13
  base (59 HIGH / 78 MEDIUM) and was reverted. Frontend remains clean at 0
  MEDIUM+ after pinning nginx 1.31.7. All backend findings are preserved, not
  suppressed.
- **Redis fallback semantics:** documented that fallback is per-process only
  and does not claim global enforcement; successful Redis requests are mirrored
  locally to prevent double allocation on transitions.
- **Regression validation:** backend **1,260 OK, 1 skipped**; frontend **10/10**
  and **127/127** with clean build/typecheck. Logs: `/tmp/opencode/phase5-final/`.

No external gate was marked PASS. PR #105 remains unmerged while the container
security gate fails on real upstream findings.

---

## Phase 6 completion (2026-11-24)

Branch `feature/alpine-backend-runtime`, stacked on PR #106.

### Confirmed defect fixed

`test_dispatch_renews_lease_during_a_long_running_task` flaked on CI. The flake
was a symptom: the dispatch **renewal thread had no exception handling**, so a
single transient SQLite error terminated the only renewal loop and leadership
lapsed silently while the task kept running. Renewal now retries on error and
reports `lease_renewal_error_type`. Added
`test_dispatch_survives_transient_lease_renewal_error`, and verified it genuinely
catches the bug by reverting the fix (test fails) and restoring it (test passes).
The original test now polls a deadline instead of asserting a fixed
`sleep(1.4)` against a 0.6 s TTL.

### Container security resolved on evidence

| Backend base | MEDIUM+ | OS findings fixable |
| --- | --- | --- |
| `python:3.12-slim` (Debian 13) | 137 | 0 of 129 |
| `python:3.12-slim-bookworm` (Debian 12) | 261 | 0 |
| `cgr.dev/chainguard/python:latest` | 8 | 8 of 8, but only a floating tag and Python 3.15 |
| `python:3.12.16-alpine3.24` (adopted) | **0** | — |

Also corrected an earlier documentation error: the `certifi`/`msgpack`/`urllib3`/
`setuptools` findings were **pip's vendored copies** (pip's `vendor.txt` pins
`setuptools==70.3.0` exactly), not Debian duplicates, which is why the earlier
pip-upgrade pins could not clear them. The runtime image is multi-stage and now
carries no pip or setuptools at all.

No ignore file, severity downgrade or `continue-on-error` was introduced. CI run
`45420717539` on `8785e468` passes all seven jobs, and the scan log confirms a
real scan (`Detected OS family="alpine" version="3.24.4"`, `pkg_num=38`).

### Regression validation (Phase 6 tree)

- Backend: **1,261 OK, 1 skipped** (1,260 + the new renewal regression test).
- Frontend on Node 22.23.5: `npm test` **10/10**, `npm run test:ui` **127/127**
  (21 files), `npm run build` and `npm run typecheck:test` exit 0.
- Playwright: **9/9 passed locally** on Node 22.23.5 once the missing X/NSS
  libraries were supplied through an unprivileged conda prefix and
  `LD_LIBRARY_PATH` (see the real-browser note above). This matches CI's browser
  job and closes a previously documented local-only blocker.
- Logs: `/tmp/opencode/phase6/`.

### Unchanged

Acceptance stays **37/40 PASS, 3 BLOCKED**; ACC-029/030/031 still need
authorized external evidence. Acceptance and the container gate are reported
separately: the container gate is now PASS on reproducible CI evidence, but that
is not an independent security approval.
