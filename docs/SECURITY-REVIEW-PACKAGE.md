# ACC-031 — Independent security-review package (preparation only)

Status: **BLOCKED**. No independent reviewer has signed off. This package
collects evidence for that reviewer; it is not a security approval.

## 1. Scope and system boundary

Research-only market-intelligence platform. Explicitly **out of scope / absent**:
broker execution, wallet private keys, transaction signing, live order routing
and market-making execution. `/api/health` reports
`paper_trading:false`, `broker_execution:false`; the MCP catalog is an allowlist
and imported execution code under `third_party/` is inert reference material.

Deployment modes: local open development (default), deployment bearer
(`API_AUTH_REQUIRED=true`), per-user sessions (`MARKET_MIND_USER_AUTH=true`),
and the documented dual-auth mode where sessions are authoritative for browser
routes. Public ingress is **not authorized**.

## 2. Threat model (summary)

| Threat | Existing control | Residual risk / external validation |
| --- | --- | --- |
| Stolen deployment bearer | fail-closed token >=32 chars, constant-time compare, duplicate-header rejection (`api_auth.py`) | Bearer-only clients are downgraded to viewer; operator must protect token distribution. |
| Credential stuffing / user enumeration | per-account+IP sliding window, doubling lockout, dummy scrypt for unknown users (`login_guard.py`, `user_auth.py`) | In-process single-host counters; restart clears them. |
| CSRF / origin spoofing | rotating CSRF cookie+header, strict Origin checks, malformed-origin fail-closed, same-origin fetch wrapper (`user_session_middleware.py`, `frontend/src/apiClient.ts`) | Requires correct `FRONTEND_ORIGINS` and trusted-proxy count on host. |
| Privilege escalation | four-role deny-by-default policy, durable SQLite ownership, unknown-resource denial (`authorization.py`) | Roles come from operator config; misconfiguration is an operator risk. |
| Rate-limit bypass | limiters wrap session enforcement, audited denials, flood-safe eviction (`rate_limit.py`, `distributed_rate_limit.py`) | Redis cooldown can transiently double allowance (bounded); ingress limits still external. |
| Secret leakage | audit redaction, DR hook/alert redaction, env-only S3 credentials, secret-free preflight (`audit_events.py`, `dr_common.py`, `s3_offhost.py`, `config_preflight.py`) | Logs/webhooks on the real host must be reviewed by the operator. |
| Backup/restore failure | SHA-256 sidecars, manifests, fingerprints, freshness status, recovery reports | Real cloud/volume/host drills are EXT-01/02, still BLOCKED. |
| Malicious market/news text | treated as untrusted data, provenance labels, no instruction execution | Provider authenticity requires licensed provider + legal review. |

## 3. Architecture references

- Backend: `docs/ARCHITECTURE.md`, `docs/FINAL_ARCHITECTURE.md`, `docs/SECURITY_IMPLEMENTATION.md`.
- Auth/session/roles: `backend/app/api_auth.py`, `user_auth.py`, `user_session_middleware.py`, `authorization.py`, `login_guard.py`, `audit_events.py`, `rate_limit.py`, `distributed_rate_limit.py`.
- Ingress/deployment: `frontend/nginx.conf`, `frontend/nginx-limits.conf`, `deploy/tls/nginx-tls.conf.example`, `docker-compose.yml`, `docs/PUBLIC-EXPOSURE-HARDENING.md`.
- DR tooling: `scripts/backup_orchestrator.py`, `restore_orchestrator.py`, `s3_offhost.py`, `service_restart_recovery.py`, `docker_volume_drill.py`, `install_schedule.py`, `config_preflight.py`, `recovery_report.py`.

## 4. Dependency inventory

Backend runtime (`backend/requirements.txt`, 5 pinned ranges): `fastapi>=0.115,<1`,
`uvicorn[standard]>=0.30,<1`, `pydantic>=2.14.3,<3`, `httpx>=0.27,<1`,
`mcp>=2.3.0,<3`. Resolved in the local audit venv: fastapi 0.165.0, pydantic
2.14.4, uvicorn 0.54.0, starlette 1.10.0, PyYAML 6.0.4 (PyYAML used by scripts).
Frontend (`frontend/package.json`): 5 runtime and 15 dev dependencies; notable
react ^18.3.1, vite ^6.4.6, vitest ^5.1.1, @xyflow/react ^13.0.2. Full locked
inventory: `frontend/package-lock.json`. Local verification toolchain: Python
3.11.6, Node 22.23.5 via nvm; GitHub Actions pins Python 3.12 (see
`.github/workflows/quality.yml`). Scanner results must be pinned to the exact
head SHA of the final reviewable PR (recorded in the final report), not to an
earlier PR head.

## 5. Security scan results (already executed)

| Scan | Command / source | Result |
| --- | --- | --- |
| Python dependencies | CI `Dependency audit` (`pip-audit -r backend/requirements.txt --progress-spinner off`) | PASS (no advisories) — run `45353077146` |
| Frontend dependencies | CI `Dependency audit` (`npm audit --audit-level=high`, includes dev dependencies) | PASS — same run |
| Filesystem vuln/misconfig/secret | CI `Trivy filesystem security scan` (`trivy fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL`) | PASS (0 findings at MEDIUM+) — same run |
| Backend tests | CI `Backend` | PASS — same run |
| Frontend/build | CI `Frontend` | PASS — same run |
| Browser / Compose | CI `Real browser responsive tests`, `Docker Compose integration` | PASS — same run |

CI run URLs and the exact reviewed head SHA are recorded in the final report
and in each PR. The run cited in earlier drafts (`45353077146`, head
`e69530045225`) predates production-script fixes and is **superseded**; only
the final PR head's run may be cited as current evidence. Local `trivy config .`
previously reported DS-0002/DS-0026 only inside git-excluded `third_party/`
reference trees; those files are not in a clean CI checkout and are not part of
the application. No independent scanner or reviewer sign-off is claimed.

## 6. Controls to be reviewed by the independent party

- **Authentication:** bearer fail-closed and dual-auth session authority; login
  throttling, lockout and timing equalisation; regression tests in
  `test_api_auth.py`, `test_login_throttle.py`, `test_auth_timing.py`,
  `test_frontend_auth_integration.py`.
- **Authorization:** role hierarchy, deny-by-default sensitive-route policy,
  durable ownership and unknown-resource denial; `test_authorization.py`,
  `test_worker_memory_ownership.py`.
- **Audit:** bounded append-only events with recursive redaction, rate-limit and
  CSRF denial events, operator-gated query endpoint; `test_audit_events.py`,
  `test_audit_api.py`, `test_security_defect_regressions.py`.
- **Secrets:** env-only credentials, no secrets in manifests/webhooks/preflight;
  `test_dr_secret_hygiene.py`, `test_s3_offhost.py`, `test_config_preflight.py`.
- **Reliability:** disk-space preflight, flood-safe rate limiting, backup
  freshness; `test_dr_storage_failure.py`, `test_backup_freshness.py`.

## 6a. Trust boundaries

| Boundary | Crossing | Control / assumption |
| --- | --- | --- |
| Browser ↔ nginx | HTTPS/TLS, cookies, CSRF token | TLS template, HttpOnly session + readable CSRF cookie, Origin allowlist; outer proxy must be the only TLS terminator or hop count must match. |
| nginx ↔ backend | loopback Docker network | `/api` only via proxy; backend has no host ports; rate/connection limits at nginx. |
| Backend ↔ SQLite volume | shared file with supervisor | Atomic claims, execution-token fencing, WAL mode; single-host only. |
| Backend ↔ operator environment | env vars, 0600 EnvironmentFile | Strict startup validation, no values logged, fail-closed token checks. |
| DR tooling ↔ S3/webhook | signed PUT/GET, HTTPS | Env-only credentials, redacted output, sha256 sidecars; real bucket/auth is external. |
| Imported `third_party/` ↔ application | inert reference files | Not imported, excluded from clean CI checkout; must never execute. |

## 6b. Backup security

Backups contain research data (no credentials). Transfers use env-only S3
credentials, SigV4 signatures and SHA-256 sidecars/manifests with database
fingerprints. Restore requires checksum/integrity verification and a clean
target; a failed overwrite is rolled back from a pre-restore snapshot with a
failed-report artifact. Retention and encryption-at-rest are operator-side
bucket settings and are **not** verified by mocks. Backup freshness is reported
by `/api/backup/status` (`never_run`/`ok`/`stale`) but never gates `/api/ready`.

## 6c. Container image scanning gap

CI runs Trivy `fs` and `config` scans and builds the Compose stack, but it does
**not** run `trivy image` against the built frontend/backend images. An
independent reviewer should add an image scan of the exact built digests; this
is listed as an outstanding evidence item, not as a PASS.

## 6d. Independent sign-off block (to be completed by the reviewer)

| Field | Value |
| --- | --- |
| Reviewer name / role | _pending_ |
| Organization | _pending_ |
| Scope reviewed / commit SHA | _pending_ |
| Report ID and date | _pending_ |
| Critical / High findings | _pending_ |
| Retest result | _pending_ |
| Decision (GO / NO-GO) | _pending_ |
| Signature | _pending_ |

ACC-031 remains BLOCKED until this block is filled by an independent reviewer.

## 7. Penetration-test scope and evidence checklist

In scope: `/api/auth/*`, role-gated admin/operator routes, watchlist/workspace/task
ownership, CSRF and Origin enforcement, rate limits, audit query, DR/S3 hook
output, shipped nginx/TLS template and Compose segmentation. Exclude production
data, real credentials, broker/order paths (absent) and multi-host scaling.

Required evidence before ACC-031 may become PASS:
1. Signed assessment report with scope, rules of engagement and reviewer identity.
2. Finding IDs with severity, reproduction, remediation and retest dates.
3. TLS scan output (protocols, ciphers, HSTS) and segmented-network verification.
4. Scan outputs for dependency/container/config checks on the reviewed commit.
5. Explicit go/no-go decision. Critical/High findings must be closed and retested.

Until then, public deployment remains **NOT READY** and ACC-031 remains BLOCKED.
See `docs/EXTERNAL-VERIFICATION-CHECKLIST.md` (EXT-03) for rollback and operators.
