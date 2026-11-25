# Operations runbook — private research stack

Owner: operator account `jovyan`. Scope: loopback-only research terminal.
Boundaries: no public ingress, no TLS public endpoint, no broker execution,
no wallet keys, no order routing. Read-only MCP only.

All operational state lives in `/home/jovyan/.market-mind-ops/`:

| Path | Purpose |
| --- | --- |
| `private.env` | 0600 environment for the stack (never commit, never print) |
| `operator-credentials.txt` | 0600 local login credentials |
| `services.json` | service definitions, dependencies, health checks |
| `supervision/` | process manager, proxy, backup scheduler, status |
| `run/*.pid` | per-service PID files |
| `logs/*.log` | per-service logs (rotated; no secrets) |
| `backups/` | verified backups + `scheduler-status.json` |
| `bootstrap.sh` | idempotent start-after-boot entry point |

## 1. Daily checks

```bash
/home/jovyan/.market-mind-ops/supervision/status.py        # human summary
/home/jovyan/.market-mind-ops/supervision/status.py --json # machine readable
```

Exit codes: `0` healthy, `1` degraded, `2` critical.
Anything other than `0` needs the matching action below.

## 2. Access

Terminal UI: <http://127.0.0.1:8080/>
Credentials: `/home/jovyan/.market-mind-ops/operator-credentials.txt` (0600).

## 3. Common actions

```bash
# Restart one service (the supervision loop will also restart it if it dies)
/home/jovyan/.market-mind-ops/supervision/service_manager.py restart backend

# Stop everything cleanly (SIGTERM, waits, then SIGKILL)
/home/jovyan/.market-mind-ops/supervision/service_manager.py stop

# Start everything (bootstrap is idempotent and safe to re-run)
/home/jovyan/.market-mind-ops/bootstrap.sh

# Tail logs
tail -f /home/jovyan/.market-mind-ops/logs/supervisor-loop.log
tail -f /home/jovyan/.market-mind-ops/logs/backend.log
tail -f /home/jovyan/.market-mind-ops/logs/backup_scheduler.log
```

## 4. Recovery procedures

### 4.1 After a host reboot

Run the bootstrap. It exits immediately if the stack is already healthy.

```bash
/home/jovyan/.market-mind-ops/bootstrap.sh
```

Permanent persistence (needs privileges this container does not have):

* systemd host: install `scripts/host/market-mind-stack.service`
* cron host: install `scripts/host/market-mind-stack.cron`
* container: append `bootstrap.sh` to the image entrypoint

### 4.2 A service will not stay up

```bash
tail -50 /home/jovyan/.market-mind-ops/logs/<service>.log
/home/jovyan/.market-mind-ops/supervision/status.py --json   # check recent_error_lines
```

If a service crash-loops more than 8 times in 5 minutes the loop stops
retrying it deliberately, to avoid a fork storm. Fix the cause, then:

```bash
/home/jovyan/.market-mind-ops/supervision/service_manager.py restart <service>
```

### 4.3 Supervisor reports `lease_unavailable`

Expected for up to 30s after a hard kill: the dead process still holds a valid
lease, and fencing is what prevents two supervisors from double-dispatching.
Wait 30s; the loop retries automatically. Do not edit the lease table.

### 4.4 Supervisor reports `not_started` / tasks stay `queued`

```bash
/home/jovyan/.market-mind-ops/supervision/service_manager.py status
# queue a probe, then confirm it completes
curl -s http://127.0.0.1:8080/api/health
```

Interrupted tasks (status `running` at crash time) are requeued by the
supervisor's own startup recovery. To force it:

```bash
POST /api/analytical-agent-tasks/recover        # requeue interrupted tasks
```

### 4.5 Restore a backup

Never restore over a live database. Stop the stack first.

```bash
cd /home/jovyan/-MARKET-MIND-AI
export MARKET_MIND_DR_STATE_DIR=/home/jovyan/.market-mind-ops/backups/.state
B=/home/jovyan/.market-mind-ops/backups/<chosen>.db

# 1. verify without touching the live DB
.venvs/backend/bin/python scripts/restore_orchestrator.py verify --backup "$B"

# 2. stop services
/home/jovyan/.market-mind-ops/supervision/service_manager.py stop

# 3. restore into a clean directory, then point the stack at it
.venvs/backend/bin/python scripts/restore_orchestrator.py restore \
  --backup "$B" --target /home/jovyan/.market-mind-ops/restore-<date>

# 4. swap in the restored file only after the digest comparison says "matched"
#    (the restore script prints content_match and foreign_key_ok)

# 5. start again and re-check
/home/jovyan/.market-mind-ops/bootstrap.sh
```

A restore is only considered successful when the orchestrator reports
`status: verified` and `comparison.status: matched`. The scheduler stores this
outcome in `backups/scheduler-status.json` on every run.

## 5. Backups

* Runs every 6 hours and once at scheduler start.
* Retention: 14 days and at most 30 files.
* Every run performs a real verify-restore; `status: verified` requires a
  matching content digest and no foreign-key violations.
* Inspect:

```bash
cat /home/jovyan/.market-mind-ops/backups/scheduler-status.json
curl -s -H "Cookie: ..." http://127.0.0.1:8080/api/backup/status
```

## 6. Security invariants (must stay true)

* `private.env` and `operator-credentials.txt` are mode 0600.
* Only `127.0.0.1:8000` and `127.0.0.1:8080` ever listen; never `0.0.0.0`.
* `/api/health` and `/api/ready` report `paper_trading: false` and
  `broker_execution: false`.
* MCP exposes exactly 6 read-only tools.
* Logs contain no credentials, tokens or hashes.

Verify in one shot:

```bash
/home/jovyan/.market-mind-ops/supervision/status.py --json | \
  python3 -c "import json,sys;d=json.load(sys.stdin);print(d['verdict'],d['boundary'])"
```

## 7. Known host limitations

This runtime is an unprivileged container: no systemd, no Docker, no sudo,
no cron. Persistence therefore depends on either a host hook (section 4.1) or
on something re-running `bootstrap.sh`. The stack survives service crashes and
graceful restarts today; it survives a full container restart only once a host
hook is installed.

## 8. Provider-independent cloud backups

The repository uses a vendor-neutral `MARKET_MIND_CLOUD_*` contract and maps it
to the existing S3-compatible adapter only at execution time. No endpoint,
bucket or credential is committed. An operator supplies them in a 0600 env file:

| Variable | Purpose |
| --- | --- |
| `MARKET_MIND_CLOUD_ENDPOINT` | HTTPS S3-compatible API root, no base path or userinfo |
| `MARKET_MIND_CLOUD_BUCKET` | dedicated test bucket |
| `MARKET_MIND_CLOUD_REGION` | provider region |
| `MARKET_MIND_CLOUD_ACCESS_KEY` / `MARKET_MIND_CLOUD_SECRET_KEY` | scoped credentials |
| `MARKET_MIND_CLOUD_PREFIX` | optional object prefix (default `market-mind/backups`) |
| `MARKET_MIND_CLOUD_ENCRYPTION_KEY` | base64 AES-256 key, **or** |
| `MARKET_MIND_CLOUD_KEY_FILE` | 0600 file containing the same key |

```bash
python3 scripts/cloud_config.py validate-config   # fail-closed, prints no values
python3 scripts/cloud_config.py describe-config   # redacted plan
python3 scripts/cloud_config.py upload --file <artifact.enc> --key <object-key>
python3 scripts/cloud_config.py download --file <artifact.enc> --key <object-key> \
  --expect-sha256 <digest>
```

Every scheduled backup is encrypted with AES-256-GCM when a key is configured,
and the encrypted artifact is integrity-verified before it can be uploaded.
The plaintext digest and authentication tag are both checked on decrypt; a
tampered artifact fails closed.

```bash
python3 scripts/backup_crypto.py encrypt --file <backup.db> --output <backup.db.enc>
python3 scripts/backup_crypto.py verify --file <backup.db.enc>
python3 scripts/backup_crypto.py decrypt --file <backup.db.enc> --output <restore.db>
```

Current local state: encryption `verified`; off-host destination `not_configured`.
The EXT-01 cloud drill is still BLOCKED until genuine endpoint/bucket/credentials
are supplied.

## 9. Non-privileged container-recovery drill

```bash
/home/jovyan/.market-mind-ops/supervision/container_recovery_drill.py
cat /home/jovyan/.market-mind-ops/container-recovery-evidence.json
```

This hard-kills the supervision loop and all four services, clears PID files and
runs `bootstrap.sh`. It verifies database integrity, a persistent worker-memory
marker, exactly-once requeue and completion of an interrupted task, supervisor
health, loopback boundaries and all four services. Evidence from the latest run:
`passed: true`, `integrity_check=ok`, one `task_requeued`, one `task_completed`.

This is **not** a host reboot test; systemd/Docker/root are unavailable here.

## 10. Security and ingress evidence

```bash
cat /home/jovyan/.market-mind-ops/internal-security-evidence.json
cat /home/jovyan/.market-mind-ops/ingress-gate-evidence.json
cat /home/jovyan/.market-mind-ops/pip-audit.json
npm audit --omit=dev --audit-level=high --offline   # from frontend/
```

Internal audit passed: access boundaries, security headers, secret hygiene,
0600 permissions, 12/12 preflight, 0 Python and 0 npm vulnerabilities, 6
read-only MCP tools. Public ingress remains **disabled** and all six gates are
BLOCKED (TLS issuance/scan, segmentation, ingress hardening, independent
security sign-off, licensed market-data/legal review, host recovery drill).
The independent review package and proposed penetration-test scope are in
`docs/SECURITY-REVIEW-PACKAGE.md`.

## 11. Unprivileged boot/login hook

The strongest hook available without root is installed at
`~/.market-mind-ops/shell-hook.sh` and sourced from `~/.bashrc` and `~/.profile`.
On an interactive shell it runs `bootstrap.sh` only when the stack is not
healthy. Opt out with `MM_NO_AUTOSTART=1`.

```bash
bash -n /home/jovyan/.bashrc
bash -n /home/jovyan/.profile
bash -n /home/jovyan/.market-mind-ops/shell-hook.sh
cat /home/jovyan/.market-mind-ops/shell-hook-evidence.json
```

Verified: after killing the supervision loop and all four services, one
interactive shell restored a HEALTHY stack. This is **not** EXT-02/G6 host
reboot evidence; root-level units remain in `scripts/host/`.

## 12. Repeatable ingress-gate validation

```bash
python3 scripts/ingress_gate_check.py > ~/.market-mind-ops/ingress-gate-evidence.json
python3 -m unittest tests.test_ingress_gate_check
```

The validator checks only local prerequisites and prints `public_ingress_enabled:
false` with all six gates BLOCKED. It never enables ingress. The independent
reviewer scope is in `docs/ACCEPTANCE-CLOSURE-EVIDENCE.md` and
`docs/SECURITY-REVIEW-PACKAGE.md`.

## 13. Licensed-data inventory

`docs/LICENSED-DATA-INVENTORY.md` records the current verified inventory:
synthetic fixture only, no live provider, no attested sources, scraper/Yahoo/
Stooq sources blocked, and a provenance checklist for legal review. Do not set
`MARKET_MIND_ATTESTED_DATA_SOURCES` until written legal approval exists.

## 14. Acceptance status and closure requirements

- Full 46-check table: `docs/ACCEPTANCE-46-STATUS.md`.
- Exact external evidence required for the 9 open checks:
  `docs/ACCEPTANCE-CLOSURE-EVIDENCE.md`.
- Do not change `docs/acceptance-inventory.json` statuses without a passing
  `python3 scripts/external_evidence.py validate --bundle <EXT bundle>` result
  from a genuine external drill.

## 15. Fresh verification pass — 2026-11-25T04:30:05Z

All checks were re-run on the current tree: backend 1300 OK/1 skipped,
frontend 146/146, health 20/20, preflight 12/12, ingress 0/6 PASS (disabled),
0 Python/npm vulnerabilities, 0 secret matches, 0600 env/credentials, loopback
listeners only. Latest backup verified and restored into a clean isolated
target; full-stack recovery drill passed. No failed tests. External blockers
and public-production NOT READY status are unchanged.
