# Browser authentication tests

The Playwright suite exercises the authentication flow in a real Chromium browser:

- invalid owner-password rejection;
- successful sign-in and session restoration after reload;
- rejection of a state-changing request without the CSRF header;
- logout and server-side session revocation.

## CI isolation

The `browser-e2e` workflow job starts the API and Vite development server on loopback, creates a temporary scrypt hash for a test-only password, and uses isolated SQLite files under the runner's temporary directory. It does not use production credentials or a hosted database. The insecure cookie flag is enabled only for this loopback-only HTTP test environment.

## Run locally

Install the frontend and Playwright dependencies:

```bash
cd frontend
npm install
npx playwright install chromium
```

In a separate terminal, start the backend with an ephemeral owner hash and isolated databases. The password below is a test fixture only; do not reuse it:

```bash
cd backend
export PYTHONPATH=.
export MARKET_MIND_AUTH_REQUIRED=true
export MARKET_MIND_OWNER_PASSWORD_HASH="$(python -c "from app.auth_crypto import hash_password; print(hash_password('e2e-only-test-password-2026'))")"
export MARKET_MIND_AUTH_DB=/tmp/market-mind-auth-e2e.sqlite
export MARKET_MIND_DB=/tmp/market-mind-e2e.sqlite
export MARKET_MIND_COOKIE_SECURE=false
export FRONTEND_ORIGINS=http://127.0.0.1:5173
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, from `frontend/`:

```bash
VITE_API_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1
npm run test:e2e
```

The local test configuration deliberately uses HTTP only on loopback. It is not a production deployment recipe. The suite is a browser-level regression check, not an independent penetration test or security certification.
