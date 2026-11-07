# Private Docker deployment (Vercel-free)

This deployment packages the React/Vite frontend as static files served by Nginx and keeps FastAPI on the internal Compose network. It is intended for **local/private use only**; the application does not currently provide user authentication or per-user authorization.

## Prerequisites

- Docker Engine with the Compose plugin.
- A host with enough disk space for images and the SQLite data volume.

## Build and start

From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

Open http://127.0.0.1:8080. The frontend proxies `/api/` requests to the internal API service. The API has no host-published port. Compose waits for the API readiness health check before starting the frontend.

Stop the stack:

```bash
docker compose down
```

The named `market_mind_data` volume persists SQLite data when containers are recreated. Do not run `docker compose down -v` unless you intentionally want to delete that volume.

## Security boundary

The frontend listener is bound to loopback (127.0.0.1), not all network interfaces. Compose drops Linux capabilities and enables `no-new-privileges`. This is deliberate: the current workspace API has no user authentication or per-user authorization. Do not publish it directly to the public internet or expose it on a shared network.

For remote access, use a separately maintained TLS reverse proxy and authentication layer in front of the loopback service. Restrict administrative access, apply request limits, and review proxy configuration before enabling access. The app remains a single-user research workspace.

No provider credentials are required. The built-in market-data adapter is synthetic-only; this deployment does not create live market connectivity. Brokerage execution, order routing, and paper trading remain disabled.

## Routine operations

```bash
# Container state and health
docker compose ps

# Recent service logs
docker compose logs --tail=200 backend frontend

# Current container resource use
docker stats --no-stream

# Confirm loopback-only published web listener
docker compose port frontend 8080

# API readiness through the frontend proxy
curl --fail http://127.0.0.1:8080/api/ready
```

The expected published web address is `127.0.0.1:8080`; the API should have no host-published port. A successful health check does not establish data freshness, provider licensing, backup recoverability, or public-deployment security.

## SQLite backup and restore

Create a backup directory before starting:

```bash
mkdir -p backups
```

Create a verified online SQLite backup:

```bash
docker compose exec -T backend python backup_database.py /backups/market_mind-$(date -u +%Y%m%dT%H%M%SZ).db --source /data/market_mind.db
```

**Note:** the current simple Compose file does not mount a host backup directory. For backups, either add a reviewed bind mount to the backend service (e.g. `./backups:/backups`) before running the command, or copy the backup out of the container with `docker cp`. Keep backups encrypted and access-controlled; never commit database files to Git.

Restore only after stopping the stack and preserving a separate copy of the current database. The restore command refuses to overwrite an existing target unless `--overwrite` is supplied:

```bash
docker compose stop
docker compose run --rm --no-deps --entrypoint python backend restore_database.py /backups/market_mind-YYYYMMDDTHHMMSSZ.db /data/market_mind.db --overwrite
docker compose up -d
```

Replace the example timestamp with the actual backup filename. Test restores against a disposable volume before relying on this procedure.

## Release gates

This packaging is not a public production release. Before any public deployment, implement and independently review authentication/authorization, TLS and ingress controls, migration/rollback procedures, observability, and a licensed market-data provider integration. Verify provider entitlements, symbol mapping, rate limits, timestamps, and stale-data handling before enabling any real feed. Automate backup retention and conduct a host-specific recovery drill.
