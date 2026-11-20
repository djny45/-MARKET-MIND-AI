# Owner authentication setup

The API now defaults to deny access to every `/api/*` route except:

- `GET /api/health`
- `GET /api/ready`
- `POST /api/auth/login`

Login uses one configured owner password, an HttpOnly opaque session cookie, a separate readable CSRF cookie, server-side SQLite session hashes, idle and absolute expiry, and logout revocation. Mutating API requests require an exact allowed Origin and an `X-CSRF-Token` header matching the CSRF cookie. The configured `FRONTEND_ORIGINS` values are parsed as exact HTTP(S) origins; wildcards, credentials, paths, query strings, fragments, and malformed ports are rejected. The same validated allowlist is used by credentialed CORS so wildcard reflection cannot expose authenticated read-only responses.

## Configure the owner password

From the repository root, generate an scrypt hash interactively:

```bash
cd backend
python create_owner_hash.py
```

The helper prompts for the password twice and prints a hash. It does not save the password or hash to a file.

Set the printed hash in the environment used to start Compose:

```bash
export MARKET_MIND_OWNER_PASSWORD_HASH='<printed-scrypt-hash>'
docker compose up --build -d
```

Do not commit the hash or place the plaintext password in a Compose file, frontend variable, shell script, or source control. Use your deployment's secret manager for persistent production configuration.

## Cookie and network settings

Compose enables `MARKET_MIND_AUTH_REQUIRED=true`, stores sessions in `/data/auth_sessions.sqlite3`, and binds the frontend only to `127.0.0.1:8080`. The default Compose cookie setting is `MARKET_MIND_COOKIE_SECURE=false` solely for that loopback-only HTTP development setup.

For any HTTPS deployment, set `MARKET_MIND_COOKIE_SECURE=true`, set `FRONTEND_ORIGINS` to the exact HTTPS origin, and terminate TLS at a reviewed reverse proxy. Never publish the backend port directly or expose the current HTTP-only Compose setup to a public network.

Optional session lifetime settings:

- `MARKET_MIND_SESSION_IDLE_TTL`: defaults to 1800 seconds.
- `MARKET_MIND_SESSION_ABSOLUTE_TTL`: defaults to 43200 seconds.
- Both values must be between 60 seconds and 30 days.

Login attempts are stored in the shared SQLite authentication database. Client identifiers are SHA-256 digests rather than raw addresses; the limiter uses an atomic write transaction, a bounded number of client keys, and expiry cleanup. It therefore coordinates processes that use the same SQLite file. It is not a distributed rate limiter and does not coordinate separate hosts or independent database files; public hosting still requires an independent security review and additional edge-level abuse controls.

## Frontend integration status

The terminal frontend now includes a single-owner sign-in gate, session bootstrap, sign-out, automatic return to sign-in when a session expires, and a shared API client that sends CSRF headers for state-changing requests. Frontend API traffic in the Compose deployment is routed through the same-origin Nginx proxy. The sign-out control checks the server response and only switches to the signed-out view after successful revocation; if revocation fails, it keeps the workspace visible and reports the failure rather than implying that the session ended. The frontend test suite covers session bootstrap, successful and failed logout behavior, CSRF header injection for state-changing requests, cookie credential inclusion, and 401 session-expiry signaling. These are component/API-client tests; they do not replace full browser-level end-to-end testing.

Interactive API documentation and the OpenAPI schema endpoints are disabled in the application to avoid exposing the route schema publicly. Health and readiness remain public for service monitoring; all other API routes require an authenticated owner session.

## Remaining deployment gates

- Keep the current Compose HTTP setup bound to loopback only.
- For HTTPS hosting, set MARKET_MIND_COOKIE_SECURE=true, configure the exact frontend origin, and terminate TLS at a reviewed reverse proxy.
- Login throttling is SQLite-backed and shared by processes using the same database file; it is not suitable as a cross-host distributed limiter.
- Complete independent security review and end-to-end browser testing before any public deployment.

This implementation does not add public registration, multi-user accounts, OAuth, or brokerage execution.

## API response hardening

The API applies conservative browser security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, and Cross-Origin-Resource-Policy) without overwriting values supplied by the application or reverse proxy. API responses default to Cache-Control: no-store so authenticated research data and auth responses are not stored by intermediaries or browsers. HSTS is added only when the ASGI request scheme is HTTPS; TLS-terminating proxies must set and validate HSTS at the edge when the app itself receives internal HTTP. This middleware does not replace a frontend Content Security Policy or reverse-proxy security review.

The header choices follow the open-source [OpenAI FastAPI web-server security guidance](https://github.com/openai/skills/blob/main/skills/.curated/security-best-practices/references/python-fastapi-web-server-security.md). Re-check the policy against the actual deployment topology before public exposure.
