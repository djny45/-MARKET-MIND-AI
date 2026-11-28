# Private research operations — exact setup (2026-11-24)

This is the operator handover for a **private, research-only** deployment. It
enables per-user sessions, keeps the API off the public network and leaves live
financial execution disabled. It does **not** enable public ingress, production
mode or any external drill. The owner performs these steps on an authorized
host; nothing here requires invented credentials.

## 0. Boundaries

- Scope: private research terminal + API on a loopback-only Docker Compose
  stack (frontend `127.0.0.1:8080`, backend not host-published).
- No broker, order routing, wallet keys, payment or real-market trade path is
  enabled. The application reports `mode=research-only`,
  `broker_execution=false`, `paper_trading=false` on `/api/health` and
  `/api/ready` (verified locally — see `docs/OPERATIONAL-READINESS-REPORT.md`).
- Public ingress stays disabled until all six public gates pass. Private mode
  intentionally does **not** set `APP_ENV=production`/`ENV_VALIDATION_STRICT`
  because strict mode requires TLS secure cookies and a deployment bearer token.
- EXT-01/02/03 remain blocked; this setup does not claim their evidence.

## 1. Prerequisites

- Linux host with Docker Engine + Compose plugin, Python 3.11+ and Node 22.12+
  only if building the frontend outside Compose.
- Repository checkout at a recorded commit (currently PR #107 head
  `fef1ba4c6c56bddab2b4cc80157e623638c1cee4`).
- A writable private data path; Compose uses the `market_mind_data` named volume.
- A secure location **outside the repository** for the 0600 env file.

Install once if running without Docker:

```bash
cd /path/to/-MARKET-MIND-AI
python3 -m venv .venvs/backend
.venvs/backend/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci)
```

## 2. Create an operator-owned 0600 environment file

Passwords are entered interactively; only scrypt hashes are written. The file
is created outside Git with mode 0600.

```bash
cd /path/to/-MARKET-MIND-AI
umask 077
PYTHONPATH=backend .venvs/backend/bin/python - <<'PY'
import json, os
from getpass import getpass
from app.auth_crypto import hash_password

admin = input("admin username [admin]: ").strip() or "admin"
admin_hash = hash_password(getpass("new admin password: "))
viewer_hash = hash_password(getpass("new viewer password: "))
values = {
    "FRONTEND_ORIGINS": "http://127.0.0.1:8080",
    "MARKET_MIND_USER_AUTH": "true",
    "MARKET_MIND_USERS": json.dumps([
        {"username": admin, "password_hash": admin_hash, "role": "admin"},
        {"username": "viewer", "password_hash": viewer_hash, "role": "viewer"},
    ]),
    "MARKET_MIND_REQUIRE_ORIGIN": "true",
    "MARKET_MIND_COOKIE_SAMESITE": "strict",
    "MARKET_MIND_SECURE_COOKIES": "false",
    "API_RATE_LIMIT_PER_MINUTE": "30",
}
path = "/secure/private.env"          # choose a path outside the checkout
with open(path, "w", encoding="utf-8") as handle:
    for key, value in values.items():
        rendered = json.dumps(value) if key == "MARKET_MIND_USERS" else value
        handle.write(f"{key}={rendered}\n")
os.chmod(path, 0o600)
print("wrote", path, "mode 0600; no plaintext password stored")
PY
```

Roles: `viewer` (read), `analyst`, `operator`, `admin` (includes environment
validation). Add extra users by appending objects in `MARKET_MIND_USERS` with
their own `scrypt$…` hashes. Never add a `password` field.

For a private LAN address instead of loopback, change `FRONTEND_ORIGINS` to the
private hostname/IP (no wildcards, no public domain) and keep the host firewall
restricted to that LAN. The preflight in the next step rejects public origins.

## 3. Verify configuration before starting

```bash
cd /path/to/-MARKET-MIND-AI
set -a; . /secure/private.env; set +a
python3 scripts/private_mode_check.py      # expect "status": "pass"
python3 scripts/config_preflight.py --root .  # expect "status": "pass"
```

`private_mode_check.py` checks: user auth enabled, hashed users with an admin,
explicit private origins, Origin enforcement, and the checked-in loopback-only
Compose perimeter. It prints variable names only — never values. It does not
certify public deployment or external drills.

## 4. Start and verify the private stack

```bash
cd /path/to/-MARKET-MIND-AI
docker compose --env-file /secure/private.env up -d --build
bash scripts/deploy_check.sh               # no --start: env file already applied
```

Manual smoke checks (all should succeed; the protected-route code should be
`401`):

```bash
curl -fsS http://127.0.0.1:8080/healthz     # ok
curl -fsS http://127.0.0.1:8080/api/health  # mode research-only, broker_execution false
curl -fsS http://127.0.0.1:8080/api/ready   # status ready, database writable
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/api/workspaces  # 401
```

Open `http://127.0.0.1:8080/` and log in with one of the configured users.
Writes from the browser carry the `mm_csrf` cookie as `X-CSRF-Token`; direct API
writes without it receive `403`. Only the browser origin is trusted.

Stop without destroying data:

```bash
docker compose down          # NEVER docker compose down -v
```

## 5. Local verification performed for this handover (no Docker available here)

On this environment Docker/systemd are absent, so the stack was exercised
directly against an isolated database under `/tmp/opencode/ops-verify/run`:

- backend `uvicorn app.main:app` on `127.0.0.1:8000` with fixture users and
  `MARKET_MIND_REQUIRE_ORIGIN=true`;
- built frontend `frontend/dist` served on `127.0.0.1:8080` by a temporary local
  proxy that reproduces `frontend/nginx.conf`'s same-origin `/api/` routing
  (the proxy is a verification aid in `/tmp`, not a repository module);
- results: `/api/health` 200 (`research-only`, `broker_execution=false`,
  `paper_trading=false`), `/api/ready` 200 (database writable, storage ok),
  `/docs` 200, protected route unauthenticated 401, admin login 200,
  `/api/auth/me` 200, write without CSRF 403, write with CSRF 200, admin-only
  environment validation 200 for admin and 403 for viewer, frontend index 200,
  frontend-proxied health and session calls 200. No errors in the backend log.
- exact transcripts: `/tmp/opencode/ops-verify/run/summary.json` and the
  captured response files in that directory. These are local verification
  evidence, **not** Docker/host/cloud validation.

## 6. Ongoing private-mode operations

- Backups and recovery: keep the documented host schedule procedure
  (`docs/HOST-RECOVERY-PROCEDURE.md`) for the owner/admin to install; none of
  that was executed here (EXT-02 remains blocked).
- Off-host copies: S3 adapter is prepared but has no endpoint/credentials
  (EXT-01 remains blocked).
- Security: internal audits are not independent approval (EXT-03 remains
  blocked). Do not expose this stack beyond loopback/authorized LAN.
- Rotate the operator password hashes and the env file whenever a user leaves;
  revoke sessions via logout/restart. Treat the env file as a secret.
