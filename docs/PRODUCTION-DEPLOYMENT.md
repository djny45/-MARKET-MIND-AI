# Private Docker deployment (Vercel-free)

This deployment packages the React/Vite frontend as static files served by Nginx and keeps FastAPI on the internal Compose network. It is intended for **local/private use only**. The current Compose configuration requires single-owner cookie authentication on API routes; it is not a multi-user identity, RBAC, or OAuth system.

## Prerequisites

- Docker Engine with the Compose plugin.
- A host with enough disk space for images and the SQLite data volume.

## Build and start

From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

Open http://127.0.0.1:8080. The frontend proxies `/api/` requests to the internal API service. The API has no host-published port. Compose waits for the API readiness health check before starting the frontend. Compose also starts `agent-supervisor`, a separate backend-image process that polls the shared SQLite queue and executes bounded batches.

Stop the stack:

```bash
docker compose down
```

The named `market_mind_data` volume persists SQLite data when containers are recreated. Do not run `docker compose down -v` unless you intentionally want to delete that volume.

## Persistent research-task supervisor

The `agent-supervisor` service shares the `market_mind_data` volume with the API. Queue submissions are committed to SQLite before returning; the supervisor polls every 2 seconds by default, recovers stale `running` tasks at startup after a 15-minute grace period, and dispatches up to 50 queued tasks per cycle with a maximum concurrency of 4. Tune with `AGENT_SUPERVISOR_POLL_SECONDS`, `AGENT_SUPERVISOR_BATCH_SIZE`, and `AGENT_SUPERVISOR_MAX_CONCURRENCY` in `docker-compose.yml`. The API no longer schedules queued work in its own process. The polling supervisor acquires a renewable singleton lease in the shared SQLite database; only the current owner/token can claim queued tasks, and the supervisor stops dispatching after lease-renewal failure. Task claims and execution-token finalization are fenced inside SQLite write transactions to reject stale or duplicate owners. Lease renewal runs on a separate heartbeat thread with a five-minute lease and a 60-second renewal interval. This is single-host SQLite ownership and queueing, not a distributed broker, consensus protocol, or multi-host queue. The Compose health check validates that the persisted supervisor heartbeat is in the `running` state, is no more than 90 seconds old, and belongs to a process ID that still exists inside the container. The portable deployment verifier waits for the supervisor's Docker health state to become `healthy`, rather than accepting a running container alone. This is local process/heartbeat evidence, not proof of external provider availability or host-level alert delivery. Check `docker compose ps` and `docker compose logs agent-supervisor` for process status.


The portable deployment checker also verifies that `MARKET_MIND_AUTH_REQUIRED` is enabled, the configured owner hash has a valid scrypt encoding, and an unauthenticated request to a protected API route receives HTTP 401. It does not verify that the owner knows the password or that the HTTPS reverse proxy is correctly configured.

## Optional n8n workflow review and import service

The Compose file includes an **opt-in** n8n service pinned to n8n 2.47.7. It is not started by the default stack. The editor is published only on host loopback at `http://127.0.0.1:5678`; its SQLite database and encryption key persist in the separate `n8n_data` volume. The HTTP editor is for local development only—do not expose port 5678 to a LAN or the public internet.

Start the normal stack and the optional n8n service:

```bash
docker compose --profile n8n up --build -d
docker compose ps
```

Open `http://127.0.0.1:5678` and complete n8n's owner-account setup. In n8n, create an API key with only the workflow create/read permissions required by the importer. Keep the key private.

To enable the separate Market Mind importer, provide these values through the backend deployment's uncommitted `.env` file or secret manager:

```env
N8N_BASE_URL=http://n8n:5678
N8N_API_KEY=replace-with-the-n8n-api-key
N8N_REVIEWER_TOKENS_JSON={"reviewer-1":{"token":"replace-with-a-long-random-reviewer-token","roles":["reviewer"]},"importer-1":{"token":"replace-with-a-different-long-random-importer-token","roles":["importer"]}}
```

Use different high-entropy tokens for the reviewer and importer. Never commit these values, place them in frontend variables, or share them in chat. Restart the backend after setting them:

```bash
docker compose up -d --force-recreate backend
```

The workflow path is: generate/submit draft → authenticated human review → explicit importer request. The importer revalidates the approved draft and creates it in n8n inactive, then reads it back to verify `active:false`. It never activates or executes a workflow. Only the restricted manual-trigger and Set nodes are accepted. An uncertain create result is recorded and blocks retries; inspect n8n manually before any further action.

Check n8n health and logs:

```bash
curl --fail http://127.0.0.1:5678/healthz
docker compose logs --tail=100 n8n backend
```

Stop the optional service with `docker compose --profile n8n stop n8n`. Its data remains in `n8n_data`; do not use `docker compose down -v` unless you intend to delete all named volumes. This local Compose setup is a development integration, not a hardened public deployment.

## Security boundary

The frontend listener is bound to loopback (127.0.0.1), not all network interfaces. Compose drops Linux capabilities and enables `no-new-privileges`.

The current Compose stack sets `MARKET_MIND_AUTH_REQUIRED=true` and expects `MARKET_MIND_OWNER_PASSWORD_HASH` to be supplied from the host's uncommitted `.env` file or a secret manager. Generate the hash locally from the backend directory:

```bash
python create_owner_hash.py
```

Copy the generated hash into the backend environment as `MARKET_MIND_OWNER_PASSWORD_HASH`; never commit the hash or plaintext password. Configure `FRONTEND_ORIGINS` as a comma-separated list of exact browser origins, without paths or wildcards. The Compose default is `http://localhost:8080`. The frontend uses the cookie session and CSRF token flow; do not put owner credentials in frontend build variables.

Compose defaults `MARKET_MIND_COOKIE_SECURE=true`. Keep this secure default for HTTPS deployments. For the explicitly loopback-only local HTTP listener (`http://127.0.0.1:8080`), set `MARKET_MIND_COOKIE_SECURE=false` in the host's uncommitted `.env` file; never use that override on a network-accessible or HTTPS deployment. For remote HTTPS, retain `true`, configure a separately maintained TLS reverse proxy, set the exact HTTPS value in `FRONTEND_ORIGINS`, and verify proxy/origin behavior before use. Do not expose the service directly to the public internet. Login attempts are rate-limited in the shared SQLite authentication database, so API processes using the same database file share the limit. The limiter is not distributed across hosts or separate databases; retain edge-level abuse controls and obtain an independent security review before public exposure.

The authentication system is single-owner session authentication. It does not provide multiple users, registration, OAuth, or per-user role-based authorization. The separate n8n reviewer/importer role checks remain distinct and do not grant general application accounts.

No provider credentials are required. The built-in market-data adapter is synthetic-only; this deployment does not create live market connectivity. Brokerage execution and order routing remain disabled.

## Host deployment verification

After deploying to a Docker host, run the read-only verification script from the repository root:

```bash
bash scripts/deploy_check.sh
```

If the optional n8n profile is enabled, include its health, loopback binding, and backend-to-n8n network checks:

```bash
bash scripts/deploy_check.sh --with-n8n
```

To explicitly ask the script to build and start the stack before checking it:

```bash
bash scripts/deploy_check.sh --start
# or, including optional n8n
bash scripts/deploy_check.sh --start --with-n8n

# Include host-persisted backup and disposable restore verification
bash scripts/deploy_check.sh --backup-drill
```

The script checks Compose configuration, API readiness, frontend response, absence of a host-published backend port, required owner authentication and scrypt hash shape, unauthenticated denial on a protected API route, loopback-only frontend/n8n bindings, Docker health for the agent supervisor, and SQLite PRAGMA integrity_check against the persistent application database. Add `--backup-drill` to create a host-persisted SQLite backup and verify a disposable restore. It prints PASS/FAIL summaries only; it does not dump environment variables or service logs. It does not prove that the configured owner password is known, configure reviewer credentials, prove that an n8n API key is valid, or import a workflow. Keep those as separate controlled acceptance tests. A successful CI run validates the GitHub-hosted runner only; run this script on the actual target host to record host-specific evidence.

## Repository security scanning

GitHub Actions runs the open-source Trivy filesystem scanner against the repository for high/critical dependency vulnerabilities and exposed secrets. The existing dependency audit remains in place. Review findings before deployment; do not put credentials into the repository or CI output.

## Supervisor heartbeat and health
The `GET /api/analytical-agent-supervisor/status` response includes a persisted supervisor heartbeat when the dedicated supervisor process has started. It reports the process ID, instance identifier, last heartbeat time and age, polling configuration, and one of these health states: `starting`, `healthy`, `stale`, `failed`, `stopped`, or `not_started`. The stale threshold is the greater of 15 seconds or three poll intervals plus five seconds.

The heartbeat is operational telemetry, not a distributed leader-election or process-liveness guarantee. A stale heartbeat indicates that the API has not observed a recent update; confirm the actual container/process state in the deployment runtime. The task queue remains single-host SQLite.

## Read-only API load probe

After the stack is healthy, run a bounded GET-only load probe against readiness:

```bash
python scripts/load_check.py --url http://127.0.0.1:8080/api/ready --requests 120 --concurrency 8
```

The probe reports request throughput, p50/p95/max latency, HTTP status counts, and error rate. It does not log response bodies, headers, environment values, or credentials. Optional `--max-p95-ms` and `--max-error-rate` arguments add explicit acceptance thresholds. Start with modest request counts and concurrency; this is a smoke/load diagnostic, not a capacity certification or a substitute for a representative workload test.

## Routine operations

```bash
# Container state and health
docker compose ps

# Recent service logs
docker compose logs --tail=200 backend agent-supervisor frontend

# Current container resource use
docker stats --no-stream

# Confirm loopback-only published web listener
docker compose port frontend 8080

# API readiness through the frontend proxy
curl --fail http://127.0.0.1:8080/api/ready
```

The expected published web address is `127.0.0.1:8080`; the API should have no host-published port. A successful health check does not establish data freshness, provider licensing, backup recoverability, or public-deployment security.

## Supervisor restart and task-recovery drill

The research-task queue is persisted in the shared SQLite volume. To verify process-restart recovery on a disposable or maintenance deployment:

1. Confirm a recent database backup exists.
2. Submit a non-sensitive test research task and record its task ID.
3. Stop the supervisor while no task is being processed:

   ```bash
   docker compose stop agent-supervisor
   ```

4. If testing interrupted-task recovery specifically, use a controlled test fixture to mark a test task as stale-running; do not modify a production task row manually.
5. Start the supervisor again:

   ```bash
   docker compose start agent-supervisor
   docker compose ps agent-supervisor
   ```

6. Check the task status and audit events through the authenticated application API. A stale `running` task is eligible for requeue after the configured 15-minute grace period. Recovery requeues; it does not itself execute a task. The supervisor then dispatches queued tasks according to its bounded polling configuration.

Automated tests include a two-process SQLite restart simulation, stale-task recovery, recent-running-task preservation, concurrent recovery, and execution-token fencing. Those tests establish application behavior against a local test database; they do not replace a host-specific volume-loss, backup-restore, or power-failure drill.

## SQLite backup and restore

Create a backup directory before starting:

```bash
mkdir -p backups
```

Create a verified online SQLite backup:

```bash
docker compose exec -T backend python backup_database.py /backups/market_mind-$(date -u +%Y%m%dT%H%M%SZ).db --source /data/market_mind.db
```

For a host-persisted backup plus disposable restore verification, run `bash scripts/backup_restore_drill.sh [backup-directory]` while the private stack is running. The script invokes the SQLite online-backup utility, restores to a separate temporary database, copies the verified file to the host, checks SQLite integrity, and prints a SHA-256 digest. It does not provide encryption, off-host replication, retention, or key management; protect and copy the resulting backup to an approved encrypted off-host location. Never commit database files to Git.

Restore only after stopping the stack and preserving a separate copy of the current database. The restore command refuses to overwrite an existing target unless `--overwrite` is supplied:

```bash
docker compose stop
docker compose run --rm --no-deps --entrypoint python backend restore_database.py /backups/market_mind-YYYYMMDDTHHMMSSZ.db /data/market_mind.db --overwrite
docker compose up -d
```

Replace the example timestamp with the actual backup filename. Test restores against a disposable volume before relying on this procedure.

## Release gates

This packaging is not a public production release. Before any public deployment, implement and independently review authentication/authorization, TLS and ingress controls, migration/rollback procedures, observability, and a licensed market-data provider integration. Verify provider entitlements, symbol mapping, rate limits, timestamps, and stale-data handling before enabling any real feed. Automate backup retention and conduct a host-specific recovery drill.
