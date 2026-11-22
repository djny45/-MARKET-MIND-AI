# SECURITY AUDIT — current state (2026-11-22)

Scope: tracked application source, configuration, infrastructure and CI. Imported
third-party source is reference material only and was not executed.

## Controls implemented and verified

| Finding | Resolution / evidence |
| --- | --- |
| Coarse, endpoint-only authorization | `backend/app/authorization.py`: four-role hierarchy (`viewer < analyst < operator < admin`), deny-by-default `authorize()`, centralized sensitive-route policy, `OwnershipRegistry`, FastAPI role/ownership dependencies. Admin-only `/api/admin/users` and `/api/system/config`; operator-only audit events and memory review. Tests: `backend/tests/test_authorization.py` (privilege escalation, cross-user watchlist/layout/task denial). |
| No audit trail for authorization decisions | `backend/app/audit_events.py`: bounded, thread-safe append-only events with actor/role/resource/action/outcome/timestamp and recursive secret redaction; operator-protected query endpoint. Test: `test_audit_events.py`. |
| Environment validation advisory only | `backend/app/env_validation.py`: strict mode via `ENV_VALIDATION_STRICT=1` or `APP_ENV=production`; `enforce_environment()` at startup rejects weak tokens, CORS wildcards and insecure cookies. Never logs secrets. Tests in `test_env_validation.py` and a manual startup smoke test. |
| Session fixation / CSRF weaknesses | Login revokes any pre-auth session before issuing a fresh one; CSRF token rotated at login; duplicate CSRF rejected; configurable SameSite/Secure/HttpOnly; optional Origin/Referer checks; constant-time comparisons. Tests in `test_authorization.py`. |
| Insecure headers / untrusted proxy headers | `SecurityHeadersMiddleware` and stripping of untrusted `X-Forwarded-*` headers in `user_session_middleware.py`. |
| Single-process rate limiting only | `backend/app/distributed_rate_limit.py`: Redis-backed atomic `INCR`+`EXPIRE` Lua limiter with automatic in-process fallback, trusted-proxy-aware keys, health/ready/preflight exemptions. Tests: `test_distributed_rate_limit.py`. |
| Deployment-wide auth only | Both deployment bearer auth and opt-in per-user sessions remain; role/ownership checks apply when per-user auth is enabled. |
| Imported execution code | AutoHedge signing/order code, FinceptTerminal, Freqtrade live bot remain inert reference copies; never imported, installed or executed. |
| Browser risk | Read-only fetcher with allowlists/SSRF checks; Camofox isolated to localhost with no credentials. |
| Secrets | No keys in source, bundle, diagnostics or reports. Trivy secret scan clean at MEDIUM/HIGH/CRITICAL. |
| Brokerage | No code path signs transactions or routes orders; health reports `broker_execution: false`. |
| Container hardening | `frontend/Dockerfile` declares explicit non-root `USER 101`; Trivy misconfiguration scan clean. |

## Outstanding security work (blockers for public exposure)

1. **TLS ingress and network segmentation** — operator responsibility; no host
   access in this environment.
2. **Independent penetration test / formal platform security review** — not
   performed; must not be claimed.
3. **Trivy CI scope** — the local scan is clean, but the CI job still scans
   only `vuln,secret` at `HIGH,CRITICAL`. Adding `misconfig` and MEDIUM scope is
   a workflow change blocked by missing OAuth `workflow` scope (see
   `docs/TRIVY_CI_AUDIT.md`). Remedy: owner runs
   `gh auth refresh -h github.com -s workflow` and approves the device code at
   https://github.com/login/device.
4. **Ingress/proxy rate limiting** — the application limiter is defense in
   depth; proxy/ingress limits are still required for public exposure.
5. **Frontend security UI** — no authentication screens or role-based UI exist;
   server-side authz is enforced regardless.

## Safe-use statement

This is a research and paper-simulation platform suitable for **private,
operator-managed deployment only**. Do not expose it publicly until items 1–4
are resolved. Live brokerage execution, wallet private keys, transaction
signing, live order routing and market-making execution remain disabled by
design.
