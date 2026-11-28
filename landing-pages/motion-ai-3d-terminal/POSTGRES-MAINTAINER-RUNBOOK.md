# PostgreSQL maintainer runbook — guarded, non-executing procedure

Status: **HOLD / documentation only**. This runbook is not authorization to provision a database, alter Vercel settings, run production migrations, deploy, or expose the service publicly.

## 1. Current release posture

The terminal is intentionally operating in read-only demo mode with `DATABASE_URL` unset. Its database-less health response is expected to be honest (`503`, `database=unconfigured`). Local demo verification reported:

- `verify-terminal.mjs`: 34/34 PASS.
- `verify-unreachable-db.mjs`: 21/21 PASS.
- `DATABASE_URL`: unset.
- No production environment, database, deployment, merge, ingress, or financial-execution setting changed.

These results verify the demo/unreachable-database behavior only. They do not prove PostgreSQL-backed application readiness.

The companion [migration-gap assessment](POSTGRES-MIGRATION-GAP.md) and [migration implementation plan](POSTGRES-MIGRATION-PLAN.md) identify required application stores beyond the market-data-only adapter. Complete those migration waves and acceptance gates before considering this runbook's database steps.

## 2. Preconditions — all must be satisfied

Do not proceed until all of the following are documented and independently reviewed:

1. A separate maintainer decision names the exact Vercel project, environment (Preview or Production), branch and reviewed deployment SHA.
2. A PostgreSQL instance is provisioned by the project maintainer, with a dedicated least-privilege application role and TLS required.
3. Database ownership, region, backup retention, restore test, monitoring, connection limits and credential rotation are documented.
4. Every in-scope application store has a versioned migration, adapter and PostgreSQL parity/concurrency/security tests. A market-data-only adapter is insufficient.
5. Migration execution is opt-in and operator-controlled; application startup must not auto-migrate.
6. Independent security review approves the exact migration and deployment diff.
7. A tested rollback restores the prior demo configuration and verifies the previous deployment remains available.
8. Public ingress remains a separate decision requiring TLS verification, network segmentation, ingress hardening and independent penetration testing.

If any precondition is missing, stop and retain demo mode.

## 3. Provisioning outline (maintainer-owned infrastructure)

Use the approved PostgreSQL provider's console or infrastructure-as-code repository. Provision a new, dedicated database and a least-privilege role for this application. Require encrypted transport, restrict inbound network access to the deployment's approved egress path, set connection limits, enable automated backups and test a restore into a disposable database.

Do not reuse a personal database, expose a database to the public internet, commit credentials, paste credentials into chat/notebooks, or print DSN values in logs. Store the connection string only in the approved secret manager.

## 4. Local migration rehearsal (disposable database only)

After the full migration implementation exists, rehearse against a disposable PostgreSQL instance using the repository's documented migration entry point and target version. The current migration-gap assessment is authoritative for missing adapters; do not infer a complete application migration from the market-store migration.

From the terminal application directory:

```bash
cd landing-pages/motion-ai-3d-terminal
npm ci
npm run typecheck
npm run lint
npm run build
```

Use only the exact migration command documented by the implemented migration package and reviewed migration PR. Do not invent a `drizzle-kit migrate` command or assume the existing Drizzle schema covers backend SQLite/in-memory stores. Before and after the rehearsal, capture migration version, schema diff, row counts and parity results without exposing credentials or customer data.

Acceptance requires clean migration from an empty disposable database, idempotent version handling, expected schema, adapter parity for every in-scope store, permission denial tests, concurrent-write/lease tests where applicable, backup/restore, and rollback evidence. Stop on any unexpected diff, failed test or uncertain write outcome.

## 5. Configure the deployment (approval-gated; not executed here)

Only after the preconditions are complete and the maintainer explicitly authorizes the named target:

1. In Vercel, select the exact `motion-ai-3d-terminal` project and the explicitly approved environment.
2. Add `DATABASE_URL` as a sensitive secret in that environment. Never use `MARKET_MIND_API_URL` for database connectivity; it is a separate HTTP backend URL.
3. Confirm the variable target and branch scope before saving. Do not copy the secret into GitHub, source files, notebook output or chat.
4. Confirm the database network policy accepts only the intended application path.
5. Deploy the reviewed SHA to a protected preview first. Keep demo/read-only safety labeling until the database-backed checks and independent review pass.
6. Do not change Production or public ingress as an implied consequence of preview verification.

## 6. Verification and promotion gate

For the approved preview, verify:

- Startup and readiness probe connect to the intended database without leaking the DSN.
- All required migrations are at the expected version.
- Every in-scope store's parity, authorization, audit redaction, concurrency and recovery tests pass.
- The UI accurately describes data origin and does not represent synthetic fixtures as live data.
- Backend capabilities remain research-only; no broker execution, wallet signing, order routing or real-money path is enabled.
- Independent reviewer approves the exact deployment SHA and release checklist.

Only a separately authorized maintainer may run the repository's deployed verification script (for example `node scripts/verify-deployed.mjs`) against the named preview. Require exit code 0 and inspect its full assertions/output. A successful exit code alone does not authorize production promotion. Do not run it against Production without a separate explicit authorization naming the exact deployment and intended checks.

## 7. Rollback procedure

If any migration, readiness check, parity test or preview verification fails:

1. Stop promotion immediately; do not retry ambiguous writes blindly.
2. Restore the previously verified demo deployment/configuration.
3. Remove the newly added environment variable from the affected environment using the Vercel dashboard or approved secret-management procedure.
4. If a database migration has already changed schema/data, follow the reviewed down-migration or restore procedure against a verified backup. Never improvise destructive SQL.
5. Re-run the demo-mode checks and verify `DATABASE_URL` is absent from the target deployment.
6. Record the deployment SHA, migration version, rollback action and observed result without recording secrets.

## 8. Explicit non-goals

This runbook does not authorize merge, production promotion, public ingress, TLS/network changes, independent penetration-test sign-off, live market-data claims, broker execution, wallet keys, order routing or real-money transactions. Keep the project research-only.
