# Operator acceptance — private research platform

Evidence-first checklist for `djny45/-MARKET-MIND-AI`. Every item below marked
**VERIFIED** was executed in the environment noted; items marked **OWNER ACTION**
were not executed and must not be reported as passed.

Safety boundary: research-only. No real-money brokerage execution, wallet key
storage, transaction signing, autonomous live order routing or market making.
Imported execution code (AutoHedge, FinceptTerminal, Freqtrade) is inert
reference material.

## Verified evidence (2026-11-23)

Baseline commit `c2be67d4`; final merged commit `6946cfa3` (PR #92).
CI on PR #92: https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45252956328 —
all 6 jobs PASS. Post-merge CI on `main`: run `45253519171` — `success`.

| Check | Command (abbreviated) | Result |
| --- | --- | --- |
| Backend suite | `PYTHONPATH=.:./backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q` | **1116 OK, 1 skipped** |
| Frontend unit | `npm test` (node 22.23.5) | **10 passed** |
| Frontend UI | `npm run test:ui` | **123 passed / 20 files** |
| Frontend build | `npm run build`, `npm run typecheck:test` | **exit 0** |
| Dependency audits | `pip-audit -r backend/requirements.txt`; `npm audit --omit=dev` | **0 known vulnerabilities / 0 npm vulnerabilities** |
| Workflow guard tests | `unittest backend.tests.test_ci_workflow_config` | **6 OK** |
| Targeted governance/research/security | 9 modules (licensing, market data, backtest, walk-forward, workers, authorization, sessions, recovery) | **83 OK** |
| Database backup + checksum | `python3 scripts/backup_orchestrator.py run ...` | `status=completed`, sha256 `144940a3…` |
| Restore into clean target | `python3 scripts/restore_orchestrator.py restore ...` | `status=matched`, schema version match |
| Integrity + row-count parity | `dr_common.database_fingerprint` on source/restored | both `integrity=ok`, all table counts equal |
| Retention | `backup_orchestrator.py prune --retention-count 2` over 4 copies | **2 retained**, orphans removed `[]` |
| Stale DR lock | `service_restart_recovery.py run --stale-after-seconds 900` | **1 stale lock removed**, DB integrity ok |
| Process kill (`kill -9`) | isolated worker killed mid-task, then restart recovery | `requeued_interrupted_count=1`, `still_running_count=0` |
| Migration rollback | `migration_rollback.py prepare → rollback → status` on isolated DB | `status=rolled_back`, sha256 match, `integrity=ok`, bars preserved |
| S3-compatible off-host | local moto S3, `s3_offhost.py upload/download` | HTTP 200/200, SHA-256 and byte parity, `credentials_exposed=false` |
| Bounded read-only load | `scripts/load_check.py --url .../api/health --requests 120 --concurrency 8` | 120×200, error rate 0, p95 36.03 ms, `read_only=true` |
| Real browser (desktop/tablet/mobile) | CI job `npx playwright install --with-deps chromium && npm run test:e2e` | **9 passed** in CI (local run blocked, see below) |

Transcripts: `/tmp/opencode/mm-final-*.log`. Drill fixtures used isolated
databases under `/tmp/opencode/`; no production database was modified.

## Not executed in this environment (do not mark passed)

- **Docker named-volume backup/restore and Compose**: no `docker` binary. Compose
  integration is covered by the passing CI job only.
- **Real cloud S3 upload/restore**: no endpoint or credentials; local moto is a
  compatibility check, not proof of a cloud restore.
- **Host service restart (cron/systemd)**: no host init access.
- **Local real-browser tests**: Chromium is installed but cannot launch — missing
  `libnspr4.so`; no root/sudo (`no_new_privileges`). CI installs the libraries.
- **TLS issuance/scan, network segmentation, ingress, external penetration test,
  formal security review**: external operator work. Public deployment is NOT READY.
- **Real migration runner**: only the armed snapshot/rollback path is verified.
- **Multi-host execution**: intentionally not implemented; SQLite is single-host.

## Operator acceptance checklist

- [x] Clean reconciliation with origin/main; recovery branch created before work
- [x] Backend, frontend, build, audits and workflow guards executed
- [x] Backup → checksum → clean restore → integrity/row-count parity
- [x] Retention pruning, stale-lock cleanup, orphan check
- [x] Process-kill recovery with requeue and no dispatch
- [x] Migration snapshot/rollback path
- [x] Off-host S3-compatible adapter (local service, SHA-256 parity)
- [x] Bounded read-only load probe
- [x] Expanded Trivy (vuln + misconfig + secret, MEDIUM+) and browser job in CI
- [ ] Docker volume restore (needs Docker on the target host)
- [ ] Real cloud S3 restore (needs configured endpoint, bucket and credentials)
- [ ] Host service restart via systemd/cron (needs host access)
- [ ] TLS / ingress / segmentation / pentest / formal review (needs owner + external party)

## Runbook pointers

- Backup/restore: `BACKUP_RESTORE_GUIDE.md`, `docs/BACKUP_RECOVERY_DRILL.md`,
  `docs/RECOVERY_DRILL_EVIDENCE.md`.
- Migration rollback: `python3 scripts/migration_rollback.py {prepare,commit,rollback,status}`
  — operations are explicit; verify the plan and snapshot before migrating.
- Service restart: `python3 scripts/service_restart_recovery.py run --db <db> --state-dir <dir> --stale-after-seconds 900`.
- Off-host backup: `scripts/s3_offhost.py describe-config|upload|download` with
  `MARKET_MIND_S3_*` environment variables only. Never commit credentials.
- Deployment: `DEPLOYMENT_GUIDE.md`, `docs/PUBLIC-EXPOSURE-HARDENING.md`.
- Security: `SECURITY.md`, `SECURITY_AUDIT.md`, `docs/SECURITY_IMPLEMENTATION.md`,
  `docs/TRIVY_CI_AUDIT.md`.
- Monitoring/alerting: `GET /api/health`, `GET /api/ready`; `MARKET_MIND_INCIDENT_WEBHOOK_URL`
  is used by the DR scripts for best-effort alerting. No external monitoring stack
  is configured — owner action for a private deployment.
- Log rotation: `docs/OPERABILITY-HARDENING.md` covers append-only audit-log caps;
  host-level logrotate configuration for container stdout remains owner action.

## Completion scores

- **A. Application feature implementation: 100%** — all requested modules and
  backend services implemented; 1116 backend + 133 frontend tests and builds pass.
- **B. Private research-platform verification: 8/10 (80%)** — all executable local
  drills and CI checks pass; Docker-volume restore, real cloud S3 restore and host
  restart remain external. Not 10/10.
- **C. Public deployment readiness: NOT READY (0/6 external gates)** — TLS,
  network segmentation, ingress hardening, external pentest and formal review are
  unverified. No public exposure is authorized.

## Off-host backup objectives

Current verified state (not operator-agreed targets):

- **Encryption in transit**: the S3 adapter uses HTTPS-capable endpoints and SigV4
  signing; the local drill used plain HTTP against a loopback moto service only.
  Server-side/at-rest encryption is **not configured or verified**.
- **Retention**: `backup_orchestrator.py prune` supports age (`--retention-days`)
  and count (`--retention-count`) policies; the executed drill retained the 2
  newest of 4 copies and removed orphan sidecars. No production policy is set.
- **Integrity**: every backup carries a `.sha256` sidecar; restore verifies the
  checksum and compares database fingerprints before accepting the result.
- **Recovery point objective (RPO)**: not defined by the operator. The measured
  drill cadence is one verified backup per orchestrator run; continuous/WAL
  archiving is not configured, so the practical RPO is the last completed backup.
- **Recovery time objective (RTO)**: not defined by the operator. Measured local
  drill times were ~1 s for backup + restore + parity on a small isolated DB and
  ~3 s for process-kill requeue; these are not production-scale estimates.
- **Operator actions**: agree RPO/RTO, enable at-rest encryption, schedule the
  backup orchestrator, configure real `MARKET_MIND_S3_*` credentials and perform
  a real cloud restore drill before relying on off-host recovery.
