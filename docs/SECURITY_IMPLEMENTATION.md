# Security Implementation (Phase 1)

This document describes the concrete, tested security controls added to the
research API. The platform boundary is unchanged: **research only** — no live
brokerage execution, wallet keys, transaction signing, or live order routing is
added or enabled by any of these controls.

## 1. Authorization (`backend/app/authorization.py`)

* Four ordered roles: `viewer < analyst < operator < admin`. Comparisons are
  deny-by-default; unknown roles, missing actors and unknown required roles are
  always denied.
* `SENSITIVE_ROUTE_POLICY` centrally maps global sensitive route prefixes to a
  minimum role. It is enforced by `UserSessionAuthMiddleware` so newly added
  routes under a sensitive prefix cannot silently become public:

  | Route prefix | Minimum role | Category |
  | --- | --- | --- |
  | `/api/admin/` | admin | user administration |
  | `/api/environment-validation` | admin | environment validation |
  | `/api/system/config` | admin | system configuration |
  | `/api/backup/`, `/api/restore/` | admin | backup/restore |
  | `/api/security/` | operator | audit logs |
  | `POST /api/workers/{id}/memory/{id}/review` | operator | memory review |

* User-owned resources are tracked by a thread-safe `OwnershipRegistry` using
  `ResourceRef(resource_type, resource_id)`. Ownership is stamped when a
  resource is created through the API for: watchlists (`watchlist`), saved
  layouts/workspaces (`layout`), research tasks (`task`), memory items
  (`memory`) and workflow runs (`run`). Reads and mutations check ownership;
  admins retain an explicit override. Unregistered resources are treated as
  global and restricted by role only.
* The authenticated actor is bound in a `ContextVar` by the session middleware,
  so existing endpoint signatures did not need to change.
* Local development with `MARKET_MIND_USER_AUTH` disabled preserves the
  existing open research API; the primitives themselves still fail closed.

## 2. Production environment gate (`backend/app/env_validation.py`)

* Advisory by default. `ENV_VALIDATION_STRICT=1` or `APP_ENV=production`
  switches to strict mode.
* `validate_environment()` returns structured findings; `enforce_environment()`
  raises `EnvironmentValidationError` and is called from the FastAPI lifespan,
  so an insecure production configuration cannot start.
* Strict mode requires bearer auth with a token of at least 32 characters,
  rejects CORS wildcards, requires `MARKET_MIND_SECURE_COOKIES=true`, and
  rejects `SameSite=None` / unsupported `MARKET_MIND_COOKIE_SAMESITE`.
* Findings and exceptions contain only variable names — never secret values.

## 3. Session and CSRF hardening (`backend/app/user_session_middleware.py`)

* Session cookies are `HttpOnly`, `SameSite=strict` by default, and `Secure`
  when `MARKET_MIND_SECURE_COOKIES=1` or strict mode is active. The SameSite
  value is configurable via `MARKET_MIND_COOKIE_SAMESITE`.
* Login rotates both the session and CSRF token and revokes any pre-existing
  session token presented by the browser (session-fixation prevention).
* Every write request requires a CSRF header (`X-CSRF-Token`) compared in
  constant time against the server-side hash. Duplicate CSRF headers are
  rejected. Optional Origin/Referer validation is available with
  `MARKET_MIND_REQUIRE_ORIGIN=1`.
* `/api/environment-validation` is no longer session-exempt; health, readiness
  and login remain exempt.

## 4. CORS, cookies, headers and trusted proxies

* CORS keeps an explicit `FRONTEND_ORIGINS` allowlist; wildcards are rejected
  by validation (and block startup in strict mode).
* `SecurityHeadersMiddleware` adds `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, a restrictive CSP, `Cache-Control: no-store`, and HSTS
  when cookies are secure.
* `MARKET_MIND_TRUSTED_PROXY_COUNT` defaults to `0`. Untrusted
  `X-Forwarded-*` headers are stripped from the ASGI scope, so a client cannot
  spoof its address for rate limiting. When a count is configured, only the
  explicitly trusted hop is used. The header name is configurable with
  `MARKET_MIND_TRUSTED_PROXY_HEADER`.

## 5. Distributed rate limiting (`backend/app/distributed_rate_limit.py`)

* Enabled when both `REDIS_URL` and a positive `API_RATE_LIMIT_PER_MINUTE` are
  configured. The Redis path uses one atomic Lua script (`INCR` plus first-hit
  `EXPIRE`).
* Any Redis import/connection/runtime error degrades once to a bounded
  in-process sliding-window limiter rather than failing open. Every successful
  Redis request is mirrored into that local window, so a Redis outage or
  recovery transition cannot grant the same client a second full budget inside
  one window. Denials are audited with the binding backend (`redis` or
  `in-process`).
* **Fallback does not claim global enforcement.** During an outage, each
  process has its own local counter, so a single global limit cannot be
  guaranteed across processes or hosts. Operators must keep ingress/proxy rate
  limits as the outer control and treat fallback as per-process protection.
  Both the distributed and in-process middleware are active when configured;
  the effective cap is the more restrictive of the two, which is conservative.
* Health and readiness probes and CORS preflight requests are exempt.

## 6. Audit events (`backend/app/audit_events.py`)

* Append-only, bounded, thread-safe `AuditEventAggregator`. Events include
  `event_id`, `event_type`, `actor`, `actor_role`, `resource`, `action`,
  `outcome`, `timestamp` and redacted metadata.
* Secret-looking keys and inline bearer credentials are redacted before an
  event is stored. There is no API to clear the log.
* `GET /api/security/audit-events` exposes recent events to `operator`/`admin`
  roles (when user auth is enabled) and records the query itself.

## Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `MARKET_MIND_USER_AUTH` | `false` | Enable per-user sessions and all enforcement |
| `MARKET_MIND_USERS` | empty | JSON list of `{username, password_hash, role}` |
| `API_AUTH_REQUIRED` / `API_AUTH_TOKEN` | `false` / empty | Deployment-wide bearer auth |
| `ENV_VALIDATION_STRICT` / `APP_ENV` | unset | Strict startup gate |
| `FRONTEND_ORIGINS` | `http://localhost:5173` | Explicit CORS allowlist |
| `MARKET_MIND_SECURE_COOKIES` | `false` | Secure cookie flag / HSTS |
| `MARKET_MIND_COOKIE_SAMESITE` | `strict` | Cookie SameSite attribute |
| `MARKET_MIND_REQUIRE_ORIGIN` | `false` | Require matching Origin/Referer on writes |
| `MARKET_MIND_TRUSTED_PROXY_COUNT` | `0` | Number of trusted proxy hops |
| `MARKET_MIND_TRUSTED_PROXY_HEADER` | `x-forwarded-for` | Trusted client address header |
| `REDIS_URL` | unset | Redis backend for distributed rate limiting |
| `API_RATE_LIMIT_PER_MINUTE` | `0` | Per-client requests per 60s window |

## Verification

```bash
cd /tmp/opencode/MARKET-MIND-AI-target
PYTHONPATH=.:./backend python -m unittest backend.tests.test_authorization \
  backend.tests.test_audit_events backend.tests.test_distributed_rate_limit \
  backend.tests.test_env_validation -q
PYTHONPATH=.:./backend python -m unittest discover -s backend/tests -q
```

## Known limitations

* Ownership and audit state are in-process and in-memory; a multi-worker
  deployment needs a shared durable backend for the same interfaces.
* CSRF protection relies on the session cookie plus header; browser clients
  must echo the CSRF token returned at login.
* These controls are defence in depth for a research-only platform; ingress
  rate limiting and TLS termination remain deployment responsibilities.
