# Production promotion checklist — Motion AI 3D terminal

Last refreshed: 2026-11-28

Scope: promote the verified, read-only demo-mode terminal to
`https://motion-ai-3d-terminal.vercel.app`. **No merge or production promotion
is authorized by this checklist until every release gate below is independently
verified.**

## Current release snapshot

- PR: [#115](https://github.com/djny45/-MARKET-MIND-AI/pull/115)
- Current PR head: use the live head SHA displayed on [PR #115](https://github.com/djny45/-MARKET-MIND-AI/pull/115). This checklist is a snapshot; the final merge candidate is whatever exact SHA is shown there after all commits settle.
- Branch: `feature/motion-ai-3d-terminal`
- Latest complete validation before this checklist refresh: commit `838e8d4646b5c081dccffdf7f8a51486597a7568`, workflow run [46127166017](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/46127166017). Backend, Frontend, browser, Docker Compose, dependency audit, Trivy filesystem, container-image security, and optional Zulip notification all completed successfully. This documentation-only refresh creates a new PR head, so require a fresh complete run on the exact live head before merge.
- Verified dependency state committed in `0f05658d`:
  - Active app uses `drizzle-orm@1.0.0-rc.6` and
    `drizzle-kit@1.0.0-rc.6`.
  - Active lockfile has no `@esbuild-kit` subtree and no esbuild package
    affected by GHSA-67mh-4wv8-2f99.
  - Imported snapshot remains on stable Drizzle 0.45.2 / 0.31.10 and pins
    esbuild 0.25.12; no esbuild version at or below 0.24.2 remains.
  - Both regenerated lockfiles and the Drizzle v1 migration-history
    conversion output were committed by CI.
- The preceding run on `136ac52c` passed the backend Python dependency audit,
  frontend dependency audit, active terminal `npm ci`, moderate-level npm
  audit, Drizzle v1 `up` conversion and checksum comparison, `drizzle-kit
  check`, typecheck, lint, production build, HTTP terminal verification,
  unreachable-PostgreSQL regression, and imported terminal dependency audit.
  Its lockfile-sync commit succeeded; the new head must still pass the full
  workflow.
- Paper subsystem default-off guard and regression test are present in source.
  Resolve its review thread only after the current Backend job passes.
- PR #115 currently has no independent `APPROVED` review. Existing reviews
  are comments, not approval.
- PR #117 and #118 remain drafts; documented order remains #117 then #118.
- Vercel has no preview deployment for commit `0f05658d` (zero matching
  deployments returned). The previous READY preview was for an older commit.
- Current Production deployment:
  - ID: `dpl_H6PQ6EAmrWjk44UJpTgbeMaRVrGi`
  - SHA: `6166a7d588ea03b016394492caabc244c4b17fd3`
  - State: READY
  - It is stale relative to the current PR head.
- Vercel reported `api-deployments-free-per-day` (more than 100 deployments)
  for linked projects on 2026-11-28. Do not keep retrying deployments; wait
  for the quota reset.
- Preview access is protected by Vercel Authentication. No bypass was used.
  Authenticated maintainer inspection is still required.
- Production `DATABASE_URL` remains unset. No production PostgreSQL database
  was provisioned and no production migration was run. Expected runtime is
  explicitly labelled read-only synthetic demo mode.

## Hard release gates

1. **Exact-SHA CI:** all required jobs must complete successfully on the final
   PR head, including Backend, Frontend, browser, Docker Compose, dependency
   audit, Trivy filesystem, and container-image security.
2. **Independent approval:** obtain a formal GitHub `APPROVED` review from a
   reviewer other than the PR author. A bot comment or author comment does not
   satisfy this gate.
3. **Review threads:** resolve all addressed threads only after their
   regression tests and current-head checks pass.
4. **Vercel preview:** after quota reset, obtain a READY deployment associated
   with the exact final PR commit. Inspect it through an authenticated SSO
   session; do not use bypasses or temporary public share links.
5. **Promotion checklist:** update this file again with the exact READY
   deployment ID, URL, commit SHA, and evidence before promoting.
6. **Merge:** merge only after formal approval and every required check is
   green on the same commit.
7. **Promotion:** promote only the verified deployment for that merged commit.
8. **Post-promotion verification:** run the command below and require exit
   code **0**. Any nonzero exit means HOLD and investigate; do not declare
   production ready.
9. **External public-exposure hardening:** TLS ingress verification, network
   segmentation, and independent penetration testing remain required before
   public exposure. See
   [Public Exposure Hardening](../../docs/PUBLIC-EXPOSURE-HARDENING.md).

## Maintainer promotion procedure — only after all gates pass

1. In Vercel project `motion-ai-3d-terminal`, locate the deployment whose
   commit SHA exactly matches the approved, fully checked PR merge commit.
2. Confirm its state is READY and authenticate to inspect the protected
   preview. Check the actual terminal UI and API responses.
3. Confirm Production `DATABASE_URL` remains unset for the demo-mode release.
   Do not attach a database or run migrations as part of this promotion.
4. Promote that exact deployment to
   `motion-ai-3d-terminal.vercel.app`. Do not promote the stale deployment
   `dpl_H6PQ6EAmrWjk44UJpTgbeMaRVrGi`.
5. Run:

```bash
cd landing-pages/motion-ai-3d-terminal
node scripts/verify-deployed.mjs https://motion-ai-3d-terminal.vercel.app
```

Required: exit code 0, no boot fallback, full terminal served, explicit
`demo-synthetic` origin, and honest unavailable/unconfigured database health.

## Rollback

- Before promotion, leave the current Production deployment untouched.
- If post-promotion verification fails, reassign the Production domain to the
  previously serving deployment
  `dpl_H6PQ6EAmrWjk44UJpTgbeMaRVrGi` and record the rollback in the release
  evidence.
- Alternatively, revert the PR #115 merge commit on `main`, allow Vercel Git
  integration to build the revert, then rerun `verify-deployed.mjs`.
- No database rollback is expected: `DATABASE_URL` remains unset and no
  production data or schema was modified.

## Explicit HOLD conditions

- Any required check is pending, cancelled, neutral where success is required,
  or failing on the final SHA.
- No formal independent GitHub approval.
- No READY Vercel deployment for the exact final SHA.
- SSO preview inspection incomplete.
- Vercel deployment quota has not reset.
- `verify-deployed.mjs` has not returned exit code 0 after promotion.
- TLS, network segmentation, or independent penetration testing is incomplete
  before public exposure.

## Gate evidence refresh — 2026-11-28, exact head `95816bf9`

| Gate | Evidence | State |
| --- | --- | --- |
| Exact-SHA CI | Runs `46144041103`, `46144047078` — all required jobs SUCCESS on `95816bf9` | PASS |
| Backend suite | Local `1546 tests OK, 1 skipped` | PASS |
| Terminal harness | `verify-terminal.mjs` 46/46; `verify-unreachable-db.mjs` 21/21, exit 0 | PASS |
| Independent review | `reviewDecision` empty; no `APPROVED` review from a non-author; `sagarvsvyas5691` is GitHub 404 | BLOCKED — owner must name an existing reviewer or accept the recorded private-use waiver |
| Vercel preview | All four project checks fail `api-deployments-free-per-day`; no deployment for exact SHA | BLOCKED — account quota must reset; owner Vercel auth required |
| Browser inspection | No browser binary, camofox REST down, Vercel MCP unauthenticated | BLOCKED — owner must provide authenticated browser tooling |
| `DATABASE_URL` | Absent from private env; ADR-006 hold intact; intended state is unset for this release | CORRECT (hold) |
| `verify-deployed.mjs` | Not run against production; no authorized target | BLOCKED until promotion prerequisites pass |
| G1–G6 external | `ingress-gate-evidence.json`: 0/6 passed, `public_ingress_enabled: false` | BLOCKED — external human evidence required |

Owner action is required for the review, Vercel quota/auth, browser tooling, and all six external gates. No agent action can clear them without credentials, an existing reviewer account, or signed external evidence.
