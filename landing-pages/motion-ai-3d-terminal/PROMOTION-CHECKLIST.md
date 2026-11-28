# Production promotion checklist — Motion AI 3D terminal

Status: **HOLD — not authorized for promotion until release gates below are green.**

## Current release candidate

- PR: https://github.com/djny45/-MARKET-MIND-AI/pull/115
- Candidate branch: `feature/motion-ai-3d-terminal`
- Current candidate baseline: `f083767ecfeb296908c7cd64449339319452d613`
- Candidate Vercel deployment: `dpl_9Vv9SpPqrxDpeZUdk4F5edgLaRnB`
- Candidate preview URL: https://motion-ai-3d-terminal-l6uu52mcl-djny45s-projects.vercel.app
- Preview status: READY; deployment is associated with the candidate commit.
- Production deployment: `dpl_H6PQ6EAmrWjk44UJpTgbeMaRVrGi`, commit `6166a7d588ea03b016394492caabc244c4b17fd3`.
- `DATABASE_URL`: intentionally unset; no PostgreSQL provisioning or migration is authorized by this release.

## Required gates

1. Resolve the active terminal dependency audit finding. The isolated audit found four moderate advisories through the active app's Drizzle Kit dependency chain:
   `drizzle-kit@0.31.10 -> @esbuild-kit/esm-loader@2.6.5 -> @esbuild-kit/core-utils@3.3.2 -> esbuild@0.18.20`.
   Do not suppress audit findings, apply `npm audit fix --force`, or downgrade Drizzle Kit to 0.18.1. The proposed upgrade to Drizzle Kit 1.0 RC is not accepted until the package lock is regenerated reproducibly and TypeScript, lint, build, CLI configuration, and tests pass. Maintain a dedicated remediation PR until then.
2. PR #115 must receive a formal `APPROVED` GitHub review from an authorized reviewer. A COMMENTED review or a positive comment is not approval.
3. All required checks must be completed successfully on the final PR head. No pending/running checks and no failed audit/security jobs.
4. Complete authorized maintainer review of PRs #117 and #118; assess the planned order (#117 schema foundation before #118 parity tests) and obtain required approvals before either merge. These PRs are currently drafts and not part of this UI release's promotion gate unless the release scope changes.
5. A maintainer must open the Vercel preview using the project's authenticated Vercel SSO session and visually verify the application. Do not bypass SSO.
6. Confirm the target candidate's exact commit SHA and Vercel READY state immediately before promotion.
7. Confirm `DATABASE_URL` remains unset in Vercel Production. The candidate is expected to operate in explicitly labelled synthetic demo mode without a database; this release does not claim PostgreSQL persistence readiness.
8. Promote only after the above preconditions are satisfied and explicit operator approval for the production action is present.

## Promotion procedure

In the Vercel dashboard, project `motion-ai-3d-terminal` -> Deployments:
- Select the exact approved, READY deployment for the final approved commit.
- Confirm Git branch, full commit SHA, project and target domain.
- Assign `motion-ai-3d-terminal.vercel.app` using the standard Promote to Production action.
- Do not use deployment protection bypass or change database settings.

## Post-promotion verification (required; exit code 0)

From `landing-pages/motion-ai-3d-terminal`:

```bash
node scripts/verify-deployed.mjs https://motion-ai-3d-terminal.vercel.app
```

Require all nine checks to pass. Confirm:
- Homepage is the full terminal, not the old boot screen.
- Demo/synthetic data is clearly labelled.
- `/api/market` returns HTTP 200 with `dataOrigin: demo-synthetic`.
- `/api/health` honestly reports database unconfigured and demo mode.
- `/api/backend` reports disabled/unavailable when no backend is configured.
- No brokerage execution, live order routing, wallet signing, or autonomous-agent claims are introduced.

## Rollback

If post-promotion verification fails, immediately use Vercel dashboard to restore the recorded prior production deployment:
`dpl_H6PQ6EAmrWjk44UJpTgbeMaRVrGi`.
Then record the failure, preserve deployment logs, and open a corrective PR. No database rollback is expected because this release does not provision a database or run migrations.

## Known external blockers / non-claims

- Visual inspection is inaccessible to the agent without maintainer Vercel SSO. This is an operator action.
- TLS ingress, firewall/network segmentation, real off-host backup/restore, production process-kill recovery drill, and independent penetration testing remain external operational hardening tasks.
- Full PostgreSQL migration of the wider research backend is not included. Keep `DATABASE_URL` unset until a real PostgreSQL service is intentionally provisioned and separately approved.
- No production release is claimed while any required gate is pending or failed.
