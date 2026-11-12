# Authentication security pre-review

**Status: internal static review completed; independent external review outstanding.**

This document records a source-level review of the single-owner authentication implementation. It is not a penetration test, formal audit, or approval for public deployment.

## Scope inspected

- `backend/app/auth_api.py`: login, session middleware, CSRF, Origin validation, cookie settings, login throttling.
- `backend/app/auth_crypto.py`: scrypt password hashing, opaque session/CSRF token generation and digest comparison.
- `backend/app/auth_session_store.py`: SQLite session persistence, expiry, revocation and cleanup.
- `frontend/src/AuthGate.tsx` and `frontend/src/api.ts`: sign-in, session bootstrap, logout behavior, cookie credentials and CSRF header.
- Authentication API and frontend component/API-client tests.
- Compose deployment and Nginx proxy security boundaries.

## Positive controls observed

- Password verification uses salted scrypt and constant-time digest comparison.
- Raw session and CSRF tokens are not persisted; domain-separated SHA-256 digests are stored.
- Session cookies are HttpOnly, SameSite=Strict, and Secure by default in the auth implementation.
- Mutating authenticated requests require an exact allowlisted Origin and a CSRF header matching both the readable CSRF cookie and the session-bound digest.
- Workspace API routes are default-deny when authentication is enabled; only explicitly public health/readiness/login paths bypass it.
- Authentication-store failures return controlled 503 responses rather than silently granting access.
- Session idle and absolute expiry, revocation, and cleanup are implemented.
- Public OpenAPI and interactive API documentation endpoints are disabled.
- Credentialed CORS uses a strict exact-origin allowlist. Wildcards, credentials, URL paths, query strings, fragments, unsupported schemes and malformed ports are rejected.
- CORS is configured outside the authentication middleware so protected responses and preflight requests can receive appropriate CORS headers.
- Login throttling has bounded memory and does not trust arbitrary forwarded-for headers.
- The frontend retains the workspace view if logout fails, rather than falsely claiming the server session was revoked.

## Findings and required gates

### High — public deployment is not approved

The current Compose HTTP configuration intentionally sets `MARKET_MIND_COOKIE_SECURE=false` and binds the frontend to loopback. Do not expose this configuration to a LAN or public network. Any remote deployment requires reviewed TLS termination, Secure cookies, exact HTTPS origins, ingress restrictions and proxy configuration.

### High — login throttling is process-local

The login attempt map is in process memory. It resets on restart and is not shared between API workers or hosts. Keep the deployment single-process/private until a persistent shared limiter is implemented, tested for failure behavior, and reviewed.

### High — independent review and browser E2E are outstanding

The source-level review and automated unit/integration tests are not substitutes for an independent security reviewer or real-browser E2E testing. Obtain both before public exposure.

### Medium — reverse-proxy identity and throttling

The login limiter keys on the direct ASGI client address and intentionally ignores forwarded headers. Behind the current Compose proxy, this may aggregate requests under the proxy address. Do not change this by trusting arbitrary forwarded headers; define and test a trusted-proxy boundary first.

### Medium — operational storage controls

The SQLite session store restricts the database file on POSIX, but operators must still verify ownership and permissions for the containing volume, WAL/SHM sidecars, backups, and host-level snapshots. Keep the data volume private and backups encrypted and access-controlled.

### Medium — configuration changes require restart

The CORS allowlist is built when the application module initializes, while request-time Origin checks read the environment. Restart the backend after changing `FRONTEND_ORIGINS`; test the exact production origin through the real proxy before use.

## Required independent review checklist

An independent reviewer should verify at minimum:

1. Login abuse, throttling behavior, password-hash configuration, and error/timing behavior.
2. Cookie attributes, session rotation, expiry boundaries, revocation, and concurrent session requests.
3. CSRF and Origin checks across every mutating API route, including proxy and preflight behavior.
4. Middleware ordering, CORS behavior, trusted-proxy assumptions, and direct-backend network isolation.
5. SQLite file/sidecar permissions, lock behavior, backup confidentiality, and restore integrity.
6. Secret handling, logs, error responses, dependency advisories, and container privileges.
7. Real-browser tests for sign-in, refresh, expiry, CSRF rejection, logout, and failed logout.
8. Deployment ingress/TLS, firewall policy, operational monitoring, incident response, and recovery drills.

## Review decision

**Private single-host development only. Do not mark authentication as independently security-reviewed and do not enable public deployment until every high finding is closed and the independent reviewer records a signed-off result.** No brokerage credentials, order routing, or trade execution are part of this application.


## Browser E2E gate status

A dedicated GitHub Actions job, `Browser authentication E2E`, now starts the API and React frontend on loopback with isolated temporary SQLite files and a CI-only generated owner password, then runs the existing Playwright Chromium suite. The suite covers invalid credentials, session restoration after reload, CSRF rejection, and logout revocation. This job is a real-browser regression gate for the local development configuration. Its result must be checked on the exact PR head; until it passes, browser E2E remains an open gate. It does not replace independent security review or production TLS/proxy validation.
