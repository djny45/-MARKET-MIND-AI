# Operations and recovery runbook

This runbook applies to the **private, single-host Docker Compose deployment**. It is not an approval for public hosting or multi-worker execution.

## 1. Pre-flight checks

Before starting or restarting the stack:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8080/api/ready
```

The frontend is expected on loopback port 8080. The backend must remain on the internal Compose network with no published host port. A ready response confirms the API's configured readiness check only; it does not prove market-data freshness, provider availability, or backup recoverability.

## 2. Routine monitoring

Run these checks during normal operation:

```bash
# Service state and health
docker compose ps

# Recent application logs
docker compose logs --since=15m --tail=300 backend frontend

# Container resource snapshot
docker stats --no-stream

# Verify the published listener is loopback-only
docker compose port frontend 8080

# API readiness through the frontend proxy
curl --fail http://127.0.0.1:8080/api/ready
```

Investigate:
- repeated backend restarts or readiness failures;
- SQLite busy/locked, disk-full, or database I/O errors;
- growing queued-task counts or tasks remaining in `running` beyond the configured stale grace period;
- repeated task failures, lease contention, or supervisor cycles that stop unexpectedly;
- dependency-audit failures or unreviewed dependency changes.

The current repository does not provide an external metrics collector, alert manager, or always-on scheduler. These checks are operator-run. Do not interpret a successful health check as evidence that a provider is returning fresh or licensed data.

## 3. Research task recovery

The supervisor is a **single bounded cycle**, not a daemon:

`POST /api/analytical-agent-supervisor/run`

Example body:

```json
{
  "limit": 50,
  "max_concurrency": 4,
  "stale_after_seconds": 900
}
```

The endpoint is authenticated and requires CSRF and exact Origin validation. Invoke it only through the authenticated private workspace. Review the returned recovery and dispatch counts, then inspect failed task details and task audit events before retrying. Recovery requeues stale tasks; it does not automatically prove that their inputs or provider conditions are safe to repeat.

A cycle lease can remain until its one-hour expiry after an abrupt process stop. If a cycle reports lease contention, inspect process health and recent logs before attempting another cycle. The lease is scoped to processes sharing the same SQLite file, not separate hosts.

## 4. Backup

Create a verified SQLite backup using the repository helper:

```bash
mkdir -p backups
docker compose exec -T backend python backup_database.py /backups/market_mind-$(date -u +%Y%m%dT%H%M%SZ).db --source /data/market_mind.db
```

The current Compose file does not mount a host backup directory at `/backups`. Add a reviewed bind mount before using that destination, or copy the generated backup out of the container with `docker cp`. Encrypt backups, restrict access, and keep them outside the repository. Never commit database files or secrets.

Define a host-level backup cadence and retention policy appropriate to the data's value; neither is automatically configured by this repository.

## 5. Restore drill

Perform a restore drill against a **disposable volume or isolated test host**, never over the only production copy:

1. Preserve a separate copy of the current database.
2. Stop the stack.
3. Restore the backup into an isolated target using `restore_database.py`.
4. Start the isolated stack and check `/api/ready`.
5. Verify representative workspace, workflow-history, task, evidence-memory, and authentication-session records.
6. Record the backup timestamp, restore duration, validation result, and any missing data.
7. Destroy the disposable environment after the drill.

The restore helper refuses to overwrite an existing target unless `--overwrite` is supplied. Do not use that option against the only copy of a database.

## 6. Security and deployment gates

- Keep the current HTTP Compose listener bound to `127.0.0.1`; do not expose it to a LAN or public internet.
- For a separately reviewed HTTPS ingress, set `MARKET_MIND_COOKIE_SECURE=true`, configure exact HTTPS `FRONTEND_ORIGINS`, and review proxy headers, TLS termination, firewall rules, and session behavior.
- The login rate limiter is process-local. Do not scale to multiple API workers until a shared persistent limiter and its failure behavior are implemented and tested.
- Do not expose the API port directly.
- Complete independent security review and browser-level end-to-end testing before public deployment.
- Treat source provenance and evidence audit results as traceability metadata, not proof of source authenticity, claim entailment, or truth.

## 7. Incident notes

For each incident, record UTC start/end, affected service, relevant log excerpts with secrets removed, task IDs, recovery actions, backup used, and validation results. Rotate any credential that may have been exposed. Preserve the original database before attempting repair. If database integrity is uncertain, stop writes and restore into an isolated copy for diagnosis.

## Current limitations

This is an operator runbook, not an implemented monitoring or backup automation service. The queue and supervisor are single-process/single-database facilities. Public deployment, multi-host scheduling, automatic backup retention, alert delivery, and unattended scheduler authentication remain out of scope until separately implemented and reviewed.
