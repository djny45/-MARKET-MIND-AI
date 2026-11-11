# Owner authentication setup

The API now defaults to deny access to every `/api/*` route except:

- `GET /api/health`
- `GET /api/ready`
- `POST /api/auth/login`

Login uses one configured owner password, an HttpOnly opaque session cookie, a separate readable CSRF cookie, server-side SQLite session hashes, idle and absolute expiry, and logout revocation. Mutating API requests require an exact allowed Origin and an `X-CSRF-Token` header matching the CSRF cookie.

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

The login throttle is process-local and intended only for the current single-process private deployment. Before scaling to multiple API workers or public hosting, replace it with a shared persistent limiter and complete an independent security review.

## Frontend integration status

The terminal frontend now includes a single-owner sign-in gate, session bootstrap, sign-out, automatic return to sign-in when a session expires, and a shared API client that sends CSRF headers for state-changing requests. Frontend API traffic in the Compose deployment is routed through the same-origin Nginx proxy. The sign-out control checks the server response and only switches to the signed-out view after successful revocation; if revocation fails, it keeps the workspace visible and reports the failure rather than implying that the session ended.

Interactive API documentation and the OpenAPI schema endpoints are disabled in the application to avoid exposing the route schema publicly. Health and readiness remain public for service monitoring; all other API routes require an authenticated owner session.

## Remaining deployment gates

- Keep the current Compose HTTP setup bound to loopback only.
- For HTTPS hosting, set MARKET_MIND_COOKIE_SECURE=true, configure the exact frontend origin, and terminate TLS at a reviewed reverse proxy.
- The login throttle is process-local. Replace it with a shared persistent limiter before using multiple API workers.
- Complete independent security review and end-to-end browser testing before any public deployment.

This implementation does not add public registration, multi-user accounts, OAuth, or brokerage execution.
