# Public-exposure hardening (operator runbook)

Status: **design and operator guidance, not a claim of public deployment readiness.**
This is a research-only platform. No live brokerage execution, wallet keys,
transaction signing, order routing or market-making exists. Independent
penetration testing and formal security review have NOT been performed.

## 1. TLS ingress

Terminate TLS at a dedicated reverse proxy; never publish the FastAPI service
or SQLite directly. A concrete starting template is
[`deploy/tls/nginx-tls.conf.example`](../deploy/tls/nginx-tls.conf.example).

Operator requirements:

- Use a valid certificate from a trusted CA and automate renewal (e.g. certbot).
- Allow only TLS 1.2/1.3; keep TLS 1.0/1.1 disabled.
- Redirect all plaintext HTTP to HTTPS.
- Set HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and
  `Content-Security-Policy` at the ingress (the app also sets its own headers,
  but ingress enforcement is the primary control).
- Validate the configuration with `nginx -t` before reload.
- Verify with an external TLS scanner after deployment. This is **not** done here.

## 2. Network segmentation and firewall requirements

- Place `backend`, `agent-supervisor` and the SQLite volume on a private Docker
  network (or equivalent host-only network). Only the TLS ingress may accept
  traffic from outside the host.
- Default-deny inbound. Allow only 443/tcp at the perimeter; allow SSH from a
  bastion or management subnet only.
- Deny egress from the research backend except to explicitly allowlisted data
  providers and package repositories. The local Camofox browser is
  localhost-only and carries no credentials.
- Do not expose database ports, Redis, or supervisor health endpoints publicly.
- Use a dedicated service account with least privilege and no shell access for
  the application process.

## 3. Reverse-proxy security headers

| Header | Required value | Purpose |
| --- | --- | --- |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` | Force HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Clickjacking defence |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Content-Security-Policy` | `default-src 'self'; ...` | Restrict resource origins |

Ingress must also set `X-Forwarded-Proto`, `X-Real-IP` and `X-Forwarded-For`
only from the trusted proxy. Configure `MARKET_MIND_TRUSTED_PROXY_COUNT` to the
exact number of trusted hops; the application strips untrusted forwarded
headers and uses the trusted value for rate-limit keys. A mismatch causes all
clients to share one rate-limit bucket.

## 4. Ingress-level rate limits

The application has an in-process limiter with a Redis-capable fallback, but
that is defence in depth, not a perimeter control. Configure ingress limits.

**Shipped defaults now implement this** in `frontend/nginx-limits.conf`
(zones, 429 status, `server_tokens off`) and `frontend/nginx.conf`
(per-location limits, connection cap, proxy headers, security headers
including CSP). Both files are copied into the container image
(`/etc/nginx/conf.d/00-ingress-limits.conf` before `default.conf`) and are
asserted by `backend/tests/test_ingress_config.py`, which also runs `nginx -t`
when an nginx binary is available. Keep these values unless observed traffic
justifies a change:

- `/api/`: 30 requests/minute per IP (`rate=30r/m`), burst 20, HTTP 429.
- Static routes: 120 requests/minute per IP (`rate=120r/m`), burst 40, HTTP 429.
- Concurrent connections per IP: 20 (`limit_conn`).
- `/healthz` is intentionally not rate limited.
- Tighten login/token endpoints further if per-user authentication is enabled.

A local `nginx -t` against these files was NOT executed in this environment
(no nginx binary); the parsing tests and the CI Docker job are the executable
checks. Monitor 429 rates and adjust from observed traffic. Do not disable the
application limiter because ingress limits exist.

## 5. Secure deployment configuration example

Set these in the service environment (0600 `EnvironmentFile`, never in an image
or repository):

```sh
APP_ENV=production
ENV_VALIDATION_STRICT=1
API_AUTH_REQUIRED=true
API_AUTH_TOKEN=<random >=32 chars>
MARKET_MIND_USER_AUTH=true
MARKET_MIND_USERS='[{"username":"analyst","password_hash":"<scrypt hash>","role":"analyst"}]'
MARKET_MIND_SECURE_COOKIES=true
MARKET_MIND_REQUIRE_ORIGIN=true
MARKET_MIND_TRUSTED_PROXY_COUNT=1
FRONTEND_ORIGINS=https://research.example.invalid
API_RATE_LIMIT_PER_MINUTE=30
MARKET_MIND_DB=/var/lib/market-mind/market_mind.db
MARKET_MIND_INCIDENT_WEBHOOK_URL=https://ops.example.invalid/hook
```

Production startup fails closed when mandatory configuration is missing or
weak (see `backend/app/env_validation.py`). Do not set `API_AUTH_REQUIRED`
without a strong token; the service intentionally refuses to start.

## 6. Real S3-compatible off-host backups

There is **no S3 client in this repository**. Off-host copy is performed by an
operator-supplied command hook with `{backup}`, `{sha256}`, `{name}` and
`{destination}` placeholders and no shell interpolation. For an operator-hosted
deployment:

1. Create a dedicated bucket with object-lock/versioning and server-side
   encryption; block public access.
2. Create an IAM user or role scoped to `s3:PutObject`, `s3:GetObject`,
   `s3:ListBucket` on that bucket prefix only.
3. Install and configure an S3 CLI on the host; supply credentials from the
   environment or an instance role, never from the hook command line.
4. Example hook (illustrative, not executed here):
   `aws s3 cp {backup} s3://market-mind-research/backups/{name} --sse AES256`
5. A stdlib-only prerequisite is available: `scripts/s3_offhost.py` with
   `describe-config`, `upload`, `download` and `--dry-run`. It reads credentials
   ONLY from `MARKET_MIND_S3_ENDPOINT`, `MARKET_MIND_S3_BUCKET`,
   `MARKET_MIND_S3_REGION`, `MARKET_MIND_S3_ACCESS_KEY` and
   `MARKET_MIND_S3_SECRET_KEY`, and never prints them. Validate with
   `python3 scripts/s3_offhost.py describe-config` and a `--dry-run` upload.
6. Verify a real restore from the object store into a clean directory and record
   the SHA-256 sidecar comparison. This is operator work and is **not** validated
   in this container; no credentials or endpoint exist here.

## 7. Production process-kill recovery drill (procedure, NOT executed)

This drill is destructive and must only be run in a maintenance window on a
host with verified backups.

1. Record the current supervisor PID and `SELECT COUNT(*) FROM analytical_agent_tasks WHERE status='running'`.
2. Confirm a verified backup and its `.sha256` sidecar exist off-host.
3. Send `SIGKILL` to the supervisor process; confirm the process is gone.
4. Run `python3 scripts/service_restart_recovery.py run --db <path> --state-dir <state> --stale-after-seconds 900`.
5. Assert: DR locks cleared, `PRAGMA integrity_check = ok`, stale `running`
   tasks requeued exactly once, no dispatch performed by the recovery script.
6. Restart the supervisor service and confirm heartbeat recovery.
7. Compare task counts and audit events to the pre-drill snapshot; investigate
   any difference before resuming normal operation.
8. Preserve logs and record the outcome in `docs/BACKUP_RECOVERY_DRILL.md`.

Steps 3–7 have **not** been performed in this environment (no host/init access,
no production service, no process supervision). They are operator-only work.

## 8. What is not verified here

- TLS certificate issuance, renewal and external scanning.
- Host firewall and network segmentation enforcement.
- Real S3 upload and restore.
- cron/systemd timer installation and host-level restart.
- Production process-kill drill and two-supervisor contention test.
- Independent penetration testing or formal security review.

No public deployment is authorized until these are completed and evidenced by
the operator.
