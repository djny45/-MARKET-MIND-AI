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

1. **Resolved: shared bearer privilege escalation.** When
   `API_AUTH_REQUIRED=true` without per-user auth, a bearer holder is
   explicitly downgraded to `viewer` for sensitive-route checks and receives
   403 on admin/operator routes. Regression test: `SharedBearerPrivilegeTests`.
2. **Resolved: ownership durability and unknown refs.** `OwnershipRegistry` now
   persists to SQLite (`resource_ownership`), unknown references are denied via
   `unregistered_resource`, and `visible_resource_ids` excludes unclaimed IDs.
   Regression tests: `DurableOwnershipTests`. Local development with both auth
   modes disabled remains open by design.
3. **Resolved: unprotected write routes.** `SENSITIVE_ROUTE_POLICY` now requires
   `analyst` for instrument-identifier updates, market-data store/import and
   workflow execution. Regression tests cover viewer denial and analyst access.
4. **Resolved: Origin defence.** Strict/production mode now requires
   `MARKET_MIND_REQUIRE_ORIGIN=true`; startup fails closed otherwise. Writes
   without an allowed Origin/Referer are rejected with 403.
5. **Resolved: stale roles.** Session validation re-reads the role from
   `MARKET_MIND_USERS`; demotions take effect immediately and removed users are
   treated as revoked.
6. **Resolved: proxy/limiter mismatch.** The in-process limiter now uses the
   same trusted-proxy-aware client key as the Redis limiter, and the Redis
   backend retries after a bounded cooldown instead of degrading permanently.
7. **Resolved: data labelling trust.** `/api/market-data/store` rejects
   live/delayed claims unless the source is in `MARKET_MIND_ATTESTED_DATA_SOURCES`.
   CSV imports remain server-labelled historical and fixtures synthetic.
8. **Resolved: redaction under benign keys.** Audit events now redact
   token-shaped values (43-char base64url and JWT patterns) anywhere in text,
   while preserving legitimate 64-char research hashes.
9. **Trivy CI scope.** The local scan covers `vuln,misconfig,secret` at
   MEDIUM/HIGH/CRITICAL and is clean; CI still scans `vuln,secret` at
   HIGH/CRITICAL. Expanded job is on `security/trivy-ci-scope` pending owner
   workflow scope. See `docs/TRIVY_CI_AUDIT.md`.
10. **Frontend security UI.** Authentication screens now exist, but server-side
    authz remains authoritative and role-gated UI is advisory only.
11. **Resolved: HTTP-level session-expiry enforcement.** When a session
    reaches its idle expiry, `UserSessionAuthMiddleware` now rejects the
    request with 401; regression test: `test_expired_session_is_rejected_at_http_layer`.
12. **Resolved: untrusted forwarded-header stripping.** With
    `MARKET_MIND_TRUSTED_PROXY_COUNT=0` the middleware strips `X-Forwarded-*`
    headers; regression test: `test_untrusted_forwarded_headers_are_stripped_by_default`.

## Outstanding external work

These findings were verified on integrated `main` `2cdb73c60aef20b867ee2bb563728714b9571133`
(merge of PR #89; WAL perf merge PR #88 at `dad80256` is upstream). HTTP-level
session-expiry and untrusted-XFF-stripping regressions were added in PR #89.
TLS ingress, network segmentation, ingress rate limits, independent penetration
testing and formal security review are operator/external responsibilities.
See `docs/PUBLIC-EXPOSURE-HARDENING.md` for the required configuration and
the documented process-kill drill. **No public deployment is authorized.**

## Safe-use statement

Research and paper-simulation platform for private, operator-managed
deployment only. Live brokerage execution, wallet private keys, transaction
signing, live order routing and market-making execution remain disabled by
design.
