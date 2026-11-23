# SECURITY AUDIT — current state (2026-11-23)

Scope: tracked application source, configuration, infrastructure and CI on
`origin/main` plus this audit branch. Imported third-party source is reference
material only and was not executed.

## Controls implemented and verified

| Finding | Resolution / evidence |
| --- | --- |
| Coarse, endpoint-only authorization | `backend/app/authorization.py`: four-role hierarchy (`viewer < analyst < operator < admin`), deny-by-default `authorize()`, `OwnershipRegistry`, role/ownership dependencies, `SENSITIVE_ROUTE_POLICY`. Tests: `test_authorization.py`, `test_user_auth_api.py`. |
| No audit trail for authorization decisions | `backend/app/audit_events.py`: bounded append-only events with recursive secret redaction; operator-protected query endpoint. Tests: `test_audit_events.py`. |
| Environment validation advisory only | `backend/app/env_validation.py`: strict mode via `ENV_VALIDATION_STRICT=1`/`APP_ENV=production`; startup rejects weak tokens, CORS wildcards and insecure cookies without logging secrets. Tests: `test_env_validation.py`. |
| Session fixation / CSRF weaknesses | Login revokes a pre-auth session and rotates CSRF; duplicate Authorization/CSRF rejected; SameSite/Secure/HttpOnly configurable; constant-time comparisons. Tests: `test_authorization.py`, `test_auth_crypto.py`. |
| Insecure headers / untrusted proxy headers | `SecurityHeadersMiddleware` and stripping of untrusted `X-Forwarded-*` in `user_session_middleware.py`. |
| Single-process rate limiting only | `backend/app/distributed_rate_limit.py`: Redis Lua limiter with in-process fallback and health/ready exemptions. Tests: `test_distributed_rate_limit.py`. |
| Ownership fencing gap in task side effects | **Fixed in this audit**: quality evaluation is written in the same transaction as the fenced completion; learning memory only after fenced success. Regression test in `test_analytical_agent_tasks.py`. |
| DR stale locks could delete live locks | **Fixed in this audit**: `DrLock.stale_count()` now reads each lock file; regression test in `test_recovery_drills.py`. |
| Imported execution code | AutoHedge signing/order code, FinceptTerminal and Freqtrade live bot remain inert reference copies; never imported, installed or executed. |
| Secrets | No keys in source, bundle, diagnostics or reports. Local Trivy secret scan clean at MEDIUM/HIGH/CRITICAL. |
| Brokerage | No code path signs transactions or routes orders; diagnostics report `broker_execution: false`. |
| Container hardening | `frontend/Dockerfile` declares `USER 101`. |

## Verified gaps (do not claim public readiness)

1. **Authorization is conditional.** `user_auth.enabled()` gates the role and
   ownership dependencies. With only `API_AUTH_REQUIRED` + shared bearer token,
   any token holder reaches `/api/admin/users`, `/api/system/config` and
   `/api/environment-validation`. `docker-compose.yml` sets neither auth flag
   nor strict env mode. Role separation requires `MARKET_MIND_USER_AUTH=true`
   and configured users.
2. **Unregistered resources are globally visible.** `OwnershipRegistry.is_owner`
   returns true for unknown refs; the registry is in-memory only and does not
   survive restart or multiple workers.
3. **Unprotected write routes.** `required_role_for_path()` returns no minimum
   role for several mutating routes (instrument-master identifiers,
   market-data store/import-csv, workflows/execute). Any valid session may write.
4. **Origin defence off by default.** `MARKET_MIND_REQUIRE_ORIGIN` is not
   required even in strict mode; default mitigation is SameSite cookies only.
5. **Stale roles in live sessions.** Roles are read from the identity table at
   session creation, not re-read from `MARKET_MIND_USERS` on each request.
6. **Proxy/limiter mismatch.** The in-process limiter uses the raw client
   address, ignoring trusted-proxy configuration, so all clients behind a proxy
   share one bucket. The Redis limiter does not recover after an exception.
7. **Data labelling trust.** `POST /api/market-data/store` accepts a
   caller-supplied `status`/`source` with no cross-check; synthetic data could
   be labelled live. No provider is configured; the API reports
   `no_live_provider_configured`.
8. **Redaction limitation.** Audit redaction targets secret-like keys and
   bearer patterns; a token embedded under a benign key in a text field may be
   logged (truncated at 300 chars).
9. **Trivy CI scope.** The local scan covers `vuln,misconfig,secret` at
   MEDIUM/HIGH/CRITICAL and is clean; CI still scans `vuln,secret` at
   HIGH/CRITICAL. Expanded job is on `security/trivy-ci-scope` pending owner
   workflow scope. See `docs/TRIVY_CI_AUDIT.md`.
10. **Frontend security UI.** Authentication screens now exist, but server-side
    authz remains authoritative and role-gated UI is advisory only.

## Outstanding external work

TLS ingress, network segmentation, ingress rate limits, independent penetration
testing and formal security review are operator/external responsibilities.
See `docs/PUBLIC-EXPOSURE-HARDENING.md` for the required configuration and
the documented process-kill drill. **No public deployment is authorized.**

## Safe-use statement

Research and paper-simulation platform for private, operator-managed
deployment only. Live brokerage execution, wallet private keys, transaction
signing, live order routing and market-making execution remain disabled by
design.
