# DEPLOYMENT GUIDE — private research deployment

## Prerequisites

- Docker Engine with the Compose plugin.
- A private host; public exposure is blocked until per-user auth, TLS ingress
  and an independent security review are complete.
- Node.js 22+ only if rebuilding the frontend base path with `VITE_BASE_PATH`.

## Build and start

```bash
git clone https://github.com/djny45/-MARKET-MIND-AI.git
cd -MARKET-MIND-AI
cp backend/.env.example backend/.env   # if present; edit locally, never commit
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8080`. Nginx serves the static frontend and proxies
`/api/` to the internal FastAPI service; the API is not host-published. The
`agent-supervisor` service consumes the shared SQLite queue. The named volume
`market_mind_data` persists research data.

## Optional API authentication

Set in the backend environment before remote use:

```
API_AUTH_REQUIRED=true
API_AUTH_TOKEN=<random secret, at least 32 characters>
FRONTEND_ORIGINS=https://your-private-frontend.example
```

Health and readiness stay unauthenticated. Check configuration with
`GET /api/environment-validation` — it returns findings only, never secret values.

## Optional per-user sessions

User authentication is opt-in. Generate a password hash, then define users:

```bash
PYTHONPATH=.:./backend python -c "from app.auth_crypto import hash_password; print(hash_password('choose-a-long-password'))"
```

Set the backend environment:

```
MARKET_MIND_USER_AUTH=true
MARKET_MIND_USERS=[{"username":"admin","password_hash":"<hash>","role":"admin"},{"username":"analyst","password_hash":"<hash>","role":"analyst"}]
MARKET_MIND_SECURE_COOKIES=true        # when served over HTTPS
```

Log in at `POST /api/auth/login`, send the returned `X-CSRF-Token` header on all
write requests, and use `GET /api/auth/me` / `POST /api/auth/logout`. Roles are
`viewer`, `analyst`, `operator`, `admin`; memory reviews require `operator`.
Health, readiness and environment validation stay unauthenticated.

## Optional rate limiting

`API_RATE_LIMIT_PER_MINUTE=60` enables a basic per-IP sliding window. Prefer
rate limiting at the ingress for anything beyond single-host use.

## GitHub Pages (static frontend only)

Run the "Deploy frontend to GitHub Pages" workflow with an HTTPS backend URL.
The workflow sets `VITE_BASE_PATH=/<repo>/`; `frontend/scripts/build.mjs`
rewrites asset and page references accordingly. The backend must set
`FRONTEND_ORIGINS` to the exact Pages origin. See
`docs/GITHUB-PAGES-DEPLOYMENT.md`.

## Verification

```bash
PYTHONPATH=.:./backend python -m unittest discover -s backend/tests -q
cd frontend && npm test && npm run build
docker compose ps
curl http://127.0.0.1:8080/api/health
```

## Boundaries

No live market-data provider, brokerage account or wallet is configured. Do not
use this deployment for real-money trading; the system has no such capability.
