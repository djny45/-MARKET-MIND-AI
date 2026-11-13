# Private Docker deployment (Vercel-free)

This deployment packages the React/Vite frontend as static files served by Nginx and keeps FastAPI on the internal Compose network. It is intended for **local/private use only**. The API has single-owner cookie authentication, but the current deployment is not approved for public hosting.

## Prerequisites

- Docker Engine with the Compose plugin.
- A host with enough disk space for images and the SQLite data volume.

## Configure owner authentication

Generate an scrypt password hash interactively:

```bash
cd backend
python create_owner_hash.py
```

Set the printed hash in the environment used to start Compose. Return to the repository root first:

```bash
cd ..
export MARKET_MIND_OWNER_PASSWORD_HASH='<printed-scrypt-hash>'
docker compose up --build -d
```

Do not commit the hash or place the plaintext password in a Compose file, frontend variable, shell script, or source control. Use a deployment secret manager for persistent configuration.

## Build and start

From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

Open http://127.0.0.1:8080 and sign in with the owner password. The frontend proxies `/api/` requests to the internal API service. The API has no host-published port. Compose waits for the API readiness health check before starting the frontend.

Stop the stack:

```bash
docker compose down
```

The named `market_mind_data` volume persists SQLite data when containers are recreated. Do not run `docker compose down -v` unless you intentionally want to delete that volume.

## Security boundary

The frontend listener is bound to loopback (127.0.0.1), not all network interfaces. Compose drops Linux capabilities and enables `no-new-privileges`. The API defaults to deny access to workspace routes until a valid owner session is present. Session cookies are HttpOnly; state-changing requests require the CSRF token and an exact allowed Origin.

The default Compose cookie setting `MARKET_MIND_COOKIE_SECURE=false` is only for this loopback-only HTTP development setup. For an HTTPS deployment, set `MARKET_MIND_COOKIE_SECURE=true`, configure `FRONTEND_ORIGINS` to the exact HTTPS origin, and terminate TLS at a reviewed reverse proxy. Never publish the backend port directly or expose the current HTTP-only Compose setup to a public network.

The login throttle is process-local and intended only for the current single-process private deployment. Replace it with a shared persistent limiter before scaling to multiple API workers. Complete independent security review and browser-level end-to-end testing before any public deployment.

No provider credentials are required. The built-in market-data adapter is synthetic-only; this deployment does not create live market connectivity. The workspace is for descriptive research and data-quality inspection; brokerage execution and order routing are not implemented.

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

This packaging is not a public production release. Before any public deployment, complete an independent security review, browser-level end-to-end testing, shared rate limiting for multi-worker hosting, TLS and ingress review, migration/rollback procedures, observability, backup retention and a host-specific recovery drill. Review provider entitlements, symbol mapping, rate limits, timestamps and stale-data handling before integrating any real data feed.
