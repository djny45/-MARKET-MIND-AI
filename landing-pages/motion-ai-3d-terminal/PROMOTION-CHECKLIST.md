# Production promotion checklist — Motion AI 3D terminal

Scope: promote the verified demo-mode dashboard build to
`https://motion-ai-3d-terminal.vercel.app`. **No promotion is performed by the
agent.** All steps require maintainer approval and Vercel dashboard access.

## Preconditions (verify before promotion)

1. PR #115 head is `5bb32e7e` (or newer reviewed commit); CI on that SHA is
   fully green: Backend, Frontend, Dependency audit, Trivy filesystem,
   Container image scan, Docker Compose integration, Browser responsive tests.
2. No approval is treated as implicit. PR review approval is required.
3. `DATABASE_URL` remains **unset** in the Vercel Production environment. No
   PostgreSQL is provisioned and no migration is executed for this release.
   Expected runtime state: labelled read-only synthetic demo mode.
4. The target deployment is `8KmqVoJ8YWZeSZHfxaSYTdfPaeAk` (for `5bb32e7e`)
   for project `motion-ai-3d-terminal`. Do **not** promote an older deployment
   such as `6HyKQ1m2n6pa5ArUbfVT9TQJUUHo`.

## Promotion steps (maintainer)

1. In Vercel dashboard → project `motion-ai-3d-terminal` → Deployments, select
   deployment `8KmqVoJ8YWZeSZHfxaSYTdfPaeAk` and confirm its commit SHA matches
   `5bb32e7e` and build status is Ready.
2. Assign the production domain `motion-ai-3d-terminal.vercel.app` to that
   deployment (Promote to Production). Do not bypass authentication.
3. Smoke-check with an authenticated Vercel session (`vercel curl`) if the
   project is password-protected.

## Post-promotion verification (required, exit 0)

```bash
cd landing-pages/motion-ai-3d-terminal
node scripts/verify-deployed.mjs https://motion-ai-3d-terminal.vercel.app
```

Expected: 9 PASS, including no boot screen, full terminal (>100 KB), demo
banner, `/api/market` HTTP 200 with `dataOrigin: demo-synthetic`, and honest
`/api/health` (`database: unconfigured`, `ok: false`).

Also confirm:
- Header/footer say "generated profiles"/"online", not "550 autonomous agents".
- `/api/backend` reports `disabled`/`unavailable`, never false "connected".

## Rollback plan

1. If verification fails, reassign the production domain to the previously
   serving deployment (`6HyKQ1m2n6pa5ArUbfVT9TQJUUHo`) — record its ID before
   promoting. This restores the old boot screen but avoids an unverified state.
2. Alternatively, revert PR #115 merge commit on `main` and let the Vercel Git
   integration build the revert; confirm with `verify-deployed.mjs`.
3. No database rollback is needed: no migrations ran and no production data was
   modified. Keep `DATABASE_URL` unset throughout.

## Known limitations

- Preview deployments are protected by Vercel Authentication; no SSO bypass
  was attempted by the agent. Visual preview inspection requires a maintainer.
- The full PostgreSQL persistence migration is out of scope; only market-data
  schema foundation (PR #117) and parity tests (PR #118) exist.
