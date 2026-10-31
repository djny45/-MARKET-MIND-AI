# Private Docker deployment

This deployment packages the React/Vite frontend as static files served by an unprivileged Nginx container and keeps the FastAPI service on the internal Compose network.

## Prerequisites

- Docker Engine with the Compose plugin.
- A host with enough disk space for the images and the SQLite data volume.

## Build and start

From the repository root:

```bash
docker compose -f docker-compose.production.yml up --build -d
docker compose -f docker-compose.production.yml ps
```

Open http://127.0.0.1:8080. The frontend proxies `/api/` requests to the internal API service. The API is not published on a host port. Compose waits for the API readiness health check before starting the web service.

Stop the stack:

```bash
docker compose -f docker-compose.production.yml down
```

The named `market_mind_data` volume persists the SQLite database when containers are recreated. Do not use `down -v` unless you intentionally want to delete that volume.

## Deployment security boundary

The web port is bound to loopback (127.0.0.1), not all network interfaces. Nginx also sets baseline anti-sniffing, frame-denial, referrer, and browser-permission response headers. The web image uses the unprivileged Nginx variant, and Compose drops all Linux capabilities while enabling `no-new-privileges`. This is deliberate: the current workspace API has no user authentication or per-user authorization. Do not publish it directly to the public internet or expose it on a shared network.

For remote access, place an independently maintained TLS reverse proxy and an authentication layer in front of the loopback service. Restrict administrative access, apply request limits, and review the proxy configuration before enabling access. The app remains a single-user research workspace.

No provider credentials are required by this deployment. The built-in market-data adapter is synthetic-only; the deployment does not create live market connectivity. Brokerage execution, order routing, and paper trading remain disabled.

## Container resource and runtime controls

The Compose definition applies separate memory and PID ceilings to the API and web containers, drops Linux capabilities, enables `no-new-privileges`, and rotates JSON container logs (10 MB per file, three files retained). The unprivileged Nginx image is configured to run without root privileges and is compatible with the web service's dropped-capability policy. These defaults reduce the impact of runaway processes and unbounded container logs; they are starting limits, not capacity guarantees. Review and tune them against observed workload and host capacity before deployment. Monitor host disk usage for the persistent database and backup directory separately.

## Health checks

- Web container: `GET /healthz` confirms Nginx is serving.
- API container: `GET /api/ready` confirms the API and SQLite schema are ready.
- In the UI, provider status remains the authoritative application-level indication that no live or delayed provider is configured.

Container health does not establish data freshness, market-data licensing, backup recoverability, or public-deployment security.

## Persistent data backup and restore

The API image includes `backup_database.py` and `restore_database.py`. The Compose stack mounts the host-side `./backups` directory at `/backups`; create it before starting the stack:

```bash
mkdir -p backups
```

Create an online, transactionally consistent SQLite backup while the API is running:

```bash
docker compose -f docker-compose.production.yml exec -T api python backup_database.py /backups/market_mind-$(date -u +%Y%m%dT%H%M%SZ).db --source /data/market_mind.db
```

The command checks source integrity, uses SQLite's backup API, verifies the resulting database, and prints a SHA-256 digest. Keep the backup directory encrypted and access-controlled; do not commit database files to Git.

To restore, first stop the stack and preserve a separate copy of the current database. Then restore the selected backup to the database path. The restore command refuses to overwrite an existing target unless `--overwrite` is explicitly supplied, and verifies the backup and restored database before replacing the target atomically:

```bash
docker compose -f docker-compose.production.yml stop
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint python api restore_database.py /backups/market_mind-YYYYMMDDTHHMMSSZ.db /data/market_mind.db --overwrite
docker compose -f docker-compose.production.yml up -d
```

Replace the example timestamp with the actual backup filename. Test restores against a separate disposable volume before relying on this procedure. A successful integrity check does not prove that an application-level recovery is complete; verify expected tables and representative records after restore.

## Operational release gates still open

This packaging is not a complete public production release. Before any public deployment, implement and independently review authentication/authorization, TLS and ingress controls, migration/rollback procedures, observability, and a licensed market-data provider integration. Validate provider entitlements, symbol mapping, rate limits, timestamps, and stale-data handling before enabling any real feed. Automate backup retention and conduct a host-specific recovery drill.
