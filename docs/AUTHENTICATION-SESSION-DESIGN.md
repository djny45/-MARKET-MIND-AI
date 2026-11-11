# Authentication and Authorization Design

**Status:** Proposed architecture; implementation and security review are still required.  
**Scope:** The existing single-user, private research workspace. This document does not authorize public deployment.

## Current security boundary

The API currently has no user authentication or per-user authorization. CORS is an origin policy, not an authentication mechanism. Worker IDs and memory namespaces provide application-level data scoping, not proof of caller identity. The Compose deployment therefore keeps the API on the internal network and publishes the frontend only on loopback. Keep that boundary until the implementation and review gates below are complete.

The React frontend currently calls many API routes directly. Authentication must be integrated across the shared API client and every UI surface; protecting only selected endpoints is not sufficient. The public static terminal page must also be checked for API access paths.

## Decisions

1. **Single-user first.** Implement one explicitly configured owner account. Do not imply multi-tenant isolation or add public registration.
2. **Opaque server-side sessions.** Generate high-entropy random session tokens. Send them only in an HttpOnly cookie; store only a cryptographic hash of each token server-side. Enforce absolute and idle expiry, revoke on logout, and rotate after login or privilege changes.
3. **Password handling.** Never store or log plaintext passwords. Use a vetted password-hashing implementation with an explicit work factor and a documented password-hash setup/rotation procedure. Do not put passwords or session secrets in frontend build-time variables.
4. **CSRF protection.** Use SameSite=Strict where compatible with the deployment, require a session-bound CSRF token on state-changing requests, and validate the request Origin against the configured exact frontend origin. Do not rely on CORS as CSRF protection.
5. **Cookie policy.** Set Secure when HTTPS is in use; use Path=/, HttpOnly, and a host-only cookie (no Domain). Local loopback HTTP development needs an explicit development setting; production must fail closed if secure-cookie/TLS assumptions are not met.
6. **Same-origin frontend.** Prefer the existing Nginx /api/ reverse proxy so the browser talks to one origin. Keep cross-origin credentialed CORS disabled unless a separately reviewed deployment requirement justifies changing it.
7. **Fail closed.** Missing, invalid, expired, or revoked sessions must return 401; authenticated but unauthorized requests must return 403. No fallback to a hard-coded or anonymous owner.
8. **Rate limits and audit.** Bound login attempts by source and account, use generic login failure messages, and record security events without recording passwords, raw session tokens, CSRF tokens, or sensitive request bodies.

## Route protection model

- **Public, minimal:** liveness/readiness and the login endpoint only. Health responses must not disclose environment variables, filesystem paths, provider secrets, or detailed internal diagnostics.
- **Authenticated owner:** all workspace, market-data, research, workflow, worker, memory, learning, proposal-review, staging, open-source intake/review, task-dispatch, task-audit, watchlist, and administrative routes.
- **State-changing routes:** in addition to a valid session, require CSRF validation and Origin validation. This includes POST, PUT, PATCH, and DELETE; review and dispatch actions must never be exempt.
- **WebSocket/SSE or future streaming routes:** require an authenticated handshake or a short-lived, single-use connection ticket. Do not place reusable session tokens in query strings.

The implementation phase must enumerate every registered route at startup or in a test and assert that each route is explicitly classified. A default-deny policy is required so newly added routes cannot silently become public.

## Frontend integration requirements

- Centralize API calls in one typed client that handles 401, login state, logout, and CSRF headers.
- Do not embed API keys, passwords, or long-lived bearer tokens in VITE_* variables or browser storage.
- Keep session state in the browser only as needed for UI rendering; the session credential remains in the HttpOnly cookie.
- Update every React component and the static terminal page to use the same-origin API path and handle unauthenticated responses.
- Ensure login, logout, page refresh, and expired-session behavior are covered by browser-level tests.

## Required implementation sequence

1. Add the session store, password verification, configuration validation, and focused unit tests.
2. Add login, current-session, and logout endpoints with cookie and CSRF behavior.
3. Add a default-deny route policy and a test that enumerates all FastAPI routes, allowing only the explicit public list.
4. Integrate the shared frontend API client and login/logout UI; migrate every direct API caller.
5. Add integration tests for anonymous access, valid sessions, expiry, revocation, CSRF failures, Origin mismatches, and cookie flags.
6. Add deployment documentation and a secure first-run secret/password setup. Verify Compose remains loopback-only.
7. Run the complete GitHub Actions suite and request an independent security review of the final implementation.

## Release gates

- No public deployment until authentication, authorization, CSRF, TLS/ingress, rate limiting, and audit behavior are independently reviewed.
- No route is public by accident; route-classification tests cover the complete route table.
- No session credential is readable by JavaScript or persisted in localStorage/sessionStorage.
- No secret is committed to the repository or exposed in client bundles, logs, health endpoints, or error responses.
- No reviewer-supplied identity is treated as verified identity unless it is derived from the authenticated session.
- The application remains a single-user private workspace until explicit multi-user authorization and data isolation are designed and tested.

## Explicit non-goals

This proposal does not add user registration, OAuth, multi-tenant access, public API keys, broker execution, or public hosting. It does not claim that authentication is implemented.