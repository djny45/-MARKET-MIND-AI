# PERMANENT PRIVATE MODE — MARKET-MIND-AI

Reference doc for the private research/intelligence platform. Boundaries are
enforced; see `PRIVATE-OPERATIONS-SETUP.md` (§2–4) for the launch detail and
`HOST-RECOVERY-PROCEDURE.md` / `docs/OPERATIONS-RUNBOOK.md` for host-level
runbooks.

## 1. Private access

- **URL (loopback only):** `http://127.0.0.1:8080/` — backend is not
  host-published on 8000; it is loopback-bound and reached via the proxy.
- **Per-user sessions** with 4 roles: `viewer`, `analyst`, `operator`, `admin`
  (see `MARKET_MIND_USERS` in `/home/jovyan/.market-mind-ops/private.env`, 0600).
- Browser writes require the same-origin `mm_csrf` cookie replayed as
  `X-CSRF-Token`; plain API writes return 403.
- **Hard boundaries (verified):** `broker_execution=false`,
  `paper_trading=false`, MCP allowlist read-only (6 tools, no trade/order/
  payment), public ingress disabled.

## 2. Persistent operation (this host)

Idle stack commands (no rebuild, nothing destructive):

```bash
cd /home/jovyan/.market-mind-ops
./bootstrap.sh                       # idempotent; starts supervision loop if not HEALTHY
./supervision/status.py              # -> "MARKET-MIND-AI operational status — HEALTHY"
./run.sh status | start | stop | restart
```

Managed services: `backend`, `proxy`, `supervisor`
(`app.analytical_agent_tasks`), `backup_scheduler` — per `services.json`.

## 3. Recovery

### Controlled service restart
1. `./run.sh restart` (stops proxy+backend, then restarts both).
2. Verify: `./supervision/status.py` → HEALTHY, and
   `curl -fsS http://127.0.0.1:8080/api/health` → `mode=research-only`.
3. Health-verification harness:
   `/home/jovyan/.market-mind-ops/health_check.py` (run with the backend venv:
   `/home/jovyan/-MARKET-MIND-AI/.venvs/backend/bin/python health_check.py`).
4. Degraded loop recovery: `./bootstrap.sh` only starts the supervision loop if
   none is alive (idempotent, safe).

### Host reboot (where authorized)
- Boot targets this same stack via the same `bootstrap.sh` / supervision loop;
  recommended entry points: systemd unit (`scripts/host/market-mind-stack.service`)
  or `@reboot` to `bootstrap.sh` (see `bootstrap.sh` header).
- After any boot: run the steps in (3.2)–(3.3) and the DB `/api/ready` check.

### Database restore verification
- Repeatable drill: `scripts/restore_orchestrator.py` (checksum/manifest
  verify, post-restore fingerprint compare).
- Latest verified report:
  `/home/jovyan/.market-mind-ops/backups/.state/restore-report-20261125T042824Z.json`
  — `status: restored_and_verified`, digests matched.

## 4. Monitoring, retention and privacy

- Health snapshot: `/home/jovyan/.market-mind-ops/supervision/status.py`.
- Backups (hourly) live in `/home/jovyan/.market-mind-ops/backups/`, scheduled
  by `backup_scheduler` (`on_start=True`, 6 h interval, verification recorded in
  `backups/scheduler-status.json`).
- Retention: files older than 14 days are cleaned; keep latest 30 (per
  `private.env`).
- Logs: `/home/jovyan/.market-mind-ops/logs/{backend,proxy,supervisor,supervisor-loop,backup_scheduler}.log`
  (current-cycle logs in `logs/`; rotated copies elsewhere).
- Security events (redacted): `GET /api/security/audit-events` — the private
  API asserts `secret_values_exposed: false`.
- Resource baseline (capture when facilities exist): RSS of
  backend≈96 MB, proxy≈20 MB, supervisor≈27 MB, backup_scheduler≈17 MB;
  alert if a service grows unbounded or restarts often.

## 4b. Paper trading (virtual capital — OPT-IN)

Config (`backend/app/paper_trading/config.py`): 550 registered agents,
**$500 virtual capital per agent, $275,000 total**, independent portfolios;
no sharing of balances between agents. Fees/slippage are simulated
(`commission_bps`, `slippage_bps`), with optional stop-loss/take-profit.

Boundaries: **all orders are virtual (`mode: virtual`) — `broker_execution`
stays False and there are no deposits, withdrawals, wallets or exchange orders.
The health endpoint reports `paper_trading: true` when enabled.

Live operator endpoints (session + operator role, loopback only):

- `GET /api/paper/status` — registered / initialized / actively trading counts
- `GET /api/paper/portfolios` — 550 independent portfolios, positions, P&L
- `GET /api/paper/trades?agent_id=…` — virtual trade log
- `POST /api/paper/place_order` — virtual BUY/SELL with fees/slippage/SL/TP
- `GET /api/paper/stats`, `/api/paper/trading-loop`, `/api/paper/snapshots`
- `POST /api/paper/snapshot?agent_id=…`, `GET /api/paper/reports/daily|monthly`
- `GET /api/paper/rankings`, `/api/paper/backtest/run`

Persistence: SQLite `paper_trading.db` (tables: portfolios, positions, trades,
snapshots, rankings). Continuous live-market paper trading runs as a supervised
asyncio loop (`backend/app/paper_trading/live.py`) that reads market bars and
executes virtual orders. "Actively trading" means agents with open positions
and/or trades in the persistent store — never claimed without runtime evidence.

Verification commands:

```bash
cd /home/jovyan/-MARKET-MIND-AI/backend
/home/jovyan/NexusTerm/.venv/bin/python -m pytest tests/test_paper_trading.py -q  # 9 tests
# live status (admin session via http://127.0.0.1:8080/): GET /api/paper/status
```

## 5. Forbidden by design

- Public ingress: never enable (`public_ingress_enabled=false`, gates blocked).
- Live trading/broker execution: disabled (`broker_execution=false`,
  `paper_trading=false`).
- Secrets: never print or persist tokens/passwords/API keys; operators use the
  0600 `/home/jovyan/.market-mind-ops/private.env`.

## 6. Preserved-feature checklist (verify on any restart)

- 550 registered agents (`/api/workers?limit=550` → 550; registry `valid=true`)
- 326 skills (`/api/skills` → 326)
- memory (`/api/workers/{id}/memory`), research timeline, analytics
  (`/api/analytics/performance`), dashboards (backup/security/providers) all 200
