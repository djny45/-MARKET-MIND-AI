# Operational reliability completion — 2026-11-25

Verdict: **the private research stack now self-heals across service failures and
graceful restarts, runs verified scheduled backups with real restore proof, and
reports its own health.** Public ingress and broker execution remain disabled.

The one thing this environment cannot prove is survival of a *full container
restart*, because it has no systemd, Docker, cron or sudo. That gap is closed
with an idempotent `bootstrap.sh` plus ready-to-install systemd/cron units, and
is stated honestly below rather than claimed as done.

## 1. Host capability findings (drove every decision)

| Capability | Result |
| --- | --- |
| `systemd` / `systemctl` | absent |
| `docker` / compose | absent |
| `sudo` | blocked (`no new privileges`) |
| `cron` / `crontab` | absent |
| supervisor / runit / s6 | absent |
| PID 1 | `tini -g -- start-notebook.py` (Jupyter container) |
| writable system hooks | none (`/usr/local/bin/start-notebook.d` is root-owned) |

Conclusion: persistence must be built from plain POSIX processes running as the
operator account, with host units provided as artifacts for a privileged host.

## 2. Priority 1 — agent supervisor

**Diagnosis.** `run_supervisor()` is correct; nothing ever ran it. The heartbeat
table showed `state=stopped`, pid 6562, ~5.5h stale. The supervisor is a
foreground loop (`python -m app.analytical_agent_tasks`) that the previous
launch never started — hence `continuous_daemon: separate_supervisor_process_required`.

**Fix.** It is now a first-class supervised service:

* started by the process manager with `depends_on: [backend]`,
* restarted automatically on exit,
* health-gated on a live PID,
* graceful SIGTERM handling already present in `_supervisor_main`.

**Dispatch test (real).**

| Step | Time | Result |
| --- | --- | --- |
| `POST /api/analytical-agents/worker_001/tasks/queue` | t+0 | `202 queued` |
| `task_dispatch_selected` | +1.3s | queued |
| `task_claimed` | +1.7s | → running |
| `task_completed` | +1.8s | → completed |

**Recovery test (real).** Killed pid 2513 with `SIGKILL`:

* restart attempts correctly returned `lease_unavailable` for ~30s —
  that is lease fencing working as designed, not a bug;
* after lease expiry the new process took over (`pid-2697`) and resumed;
* a task injected as `running` was requeued (`task_requeued running→queued`)
  and then dispatched and completed by the live supervisor.

Final: `supervisor_health=healthy`, heartbeat age ~1s, `registered_agent_count=550`,
`dispatch_mode=persistent_sqlite_polling`.

## 3. Priority 2 — automated backups

**Diagnosis.** `/api/backup/status` said `missing` / `never_run`: no destination
was configured and the scheduler had never been invoked. Scheduler code,
retention, journalling and restore tooling already existed in `scripts/` but
were never wired to a runtime.

**Configuration.**

* destination: `/home/jovyan/.market-mind-ops/backups` (mode 700, outside the repo)
* retention: 14 days and max 30 files
* freshness threshold: 24h (so `status: ok` is meaningful)
* interval: every 6h plus once at scheduler start

**Scheduler.** `supervision/backup_scheduler.py` runs under the process manager,
so a crash is restarted automatically (verified: killed pid 3455, replacement
pid 5911 came up and immediately produced a verified backup).

**Restore proof — not asserted, executed.**

| Check | Result |
| --- | --- |
| backup created + verified (`status: verified`) | pass |
| sha256 sidecar + manifest written | pass |
| `verify` (scratch restore) | `status: verified`, `comparison: matched` |
| full `restore` into clean target | `status: verified` |
| content digest backup vs restored | identical (`93dc775a…`) |
| foreign-key violations | `[]` |
| schema version match | true (v1) |

`status: verified` is only ever written when `content_match` and
`foreign_key_ok` are both true. A failure writes `restore_failed` and increments
`consecutive_failures`; the scheduler never reports success without a restore.

## 4. Priority 3 — persistent services

Four services are supervised: **backend** (uvicorn 127.0.0.1:8000), **proxy**
(same-origin, 127.0.0.1:8080), **supervisor**, **backup_scheduler**.

Implemented in `supervision/service_manager.py`:

* PID files, dependency ordering (`backend` → `proxy`/`supervisor`/`backup_scheduler`),
* HTTP/process health checks with per-service expectations,
* restart with backoff and a crash-loop breaker (8 restarts / 5 min) so a broken
  service cannot fork-storm the host,
* graceful shutdown: `SIGTERM` → wait 15s → `SIGKILL`,
* `flock` singleton so two supervision loops can never fight over PIDs.

**Controlled restart tests (all real).**

| Test | Result |
| --- | --- |
| kill backend with `SIGKILL` | new pid 3292 in ~10s, `HTTP 200` |
| kill supervisor with `SIGKILL` | restarted after lease expiry, `healthy` |
| kill backup scheduler with `SIGKILL` | new pid, backup re-verified |
| full loop `SIGTERM` (graceful) | all 4 stopped in 2s, **zero** orphan processes |
| cold start (no processes, no pid files) via `bootstrap.sh` | HEALTHY in ~10s |
| `bootstrap.sh` when already healthy | no-op, exit 0 |

**Reboot persistence.** `bootstrap.sh` is idempotent and refuses to run when
`private.env` is not mode 0600. Install targets:

* `scripts/host/market-mind-stack.service` (systemd, oneshot + RemainAfterExit,
  hardening `NoNewPrivileges`, `ProtectSystem=strict`)
* `scripts/host/market-mind-stack.cron` (`@reboot` + 5-minute watchdog)
* `scripts/host/logrotate.market-mind` (daily, 14 rotations, `copytruncate`)

These are **artifacts, not installed** — this container cannot install them.
That is why full-container-restart survival is listed as remaining below.

## 5. Priority 4 — monitoring

* `supervision/status.py` — human summary or `--json`; exit `0` healthy,
  `1` degraded, `2` critical. Reports PID, RSS, age, per-log recent error
  counts, backup state, disk, boundary flags and loop liveness.
* `GET /api/ops/status` (new) — same data through the API without shelling out.
  When user auth is enabled it is operator/admin only: verified `401` anonymous,
  `403` viewer, `200` admin. With auth disabled (a non-default, private-mode
  configuration) the role guard is a no-op, as for every other protected route;
  the endpoint remains read-only and returns no secrets.
  Covered by 6 new tests including one that fails if command-execution symbols
  appear in the handler.
* Logging: per-service logs under `logs/`, rotation provided via logrotate
  artifact. Secret scan across all logs: **0 matches**.
* Documented in `docs/OPERATIONS-RUNBOOK.md` (daily checks, restart, crash-loop,
  lease, restore, security invariants, host limitations).

## 6. Priority 5 — external dependencies

EXT-01, EXT-02 and EXT-03 remain **BLOCKED**. No credential, approval or
external evidence was invented. Everything added here is local operational
work and does not advance any external gate.

## 7. Safety verification

| Invariant | Evidence |
| --- | --- |
| Loopback only | listeners `0100007F:8000`, `0100007F:8080`; no `0.0.0.0` for the stack (port 8888 is the pre-existing Jupyter server) |
| No live broker | `/api/health` + `/api/ready` report `paper_trading=false`, `broker_execution=false` |
| MCP read-only | exactly 6 tools, unchanged |
| No secret exposure | logs 0 matches; `private.env`, credentials and backup status all mode 600; scheduler status carries no secrets |
| Public ingress | disabled |

## 8. Regression evidence

| Suite | Result |
| --- | --- |
| Full backend suite | **1300 tests OK, 1 skipped** (1275 baseline + 25 new) |
| Supervisor/task suites | **68 OK** |
| S3 off-host adapter suites | **17 OK** |
| Cloud config + backup encryption suites | **8 OK** |
| Internal security audit | PASS, 0 Critical/High |
| Skill/n8n suites | **58 OK** |
| Live health harness | **20/20** |
| Frontend node tests | **10/10** |
| Frontend UI tests | **127/127 (21 files)** |
| Frontend typecheck + production build | **PASS** |
| Playwright E2E | **9/9** |
| CI workflow YAML (3 files) | **VALID** |
| Config preflight | **12/12 PASS** |
| Operational status | HEALTHY, exit 0 |

Full command-by-command evidence: `docs/FINAL-VALIDATION-EVIDENCE.md`.

## 9. Blocker status after production-readiness execution

| Blocker | Status | Evidence / dependency |
| --- | --- | --- |
| EXT-01 cloud backup/restore | **BLOCKED** | Provider-independent config and AES-256-GCM encryption implemented; local encrypted restore drill passed. No endpoint/bucket/credentials exist. |
| EXT-02 host recovery | **BLOCKED** | Non-privileged full-stack recovery drill passed; no root/systemd/Docker host drill. |
| EXT-03 independent review | **BLOCKED** | Internal audit passed; no independent reviewer or signed decision. |
| Full container reboot survival | **BLOCKED** | Full process-tree kill + bootstrap passed; no privileged host boot hook installable. |
| Public ingress gates | **BLOCKED 0/6** | `scripts/ingress_gate_check.py` validates local prerequisites; public ingress disabled. |
| Real off-host copy | **BLOCKED** | `offhost_verification: not_configured`; no cloud destination. |

No blocked item was marked complete and no external evidence was fabricated.

## 10. Completion (verified accounting)

| Dimension | Verified result | Percentage |
| --- | --- | --- |
| Acceptance inventory (`acceptance-inventory.json`) | 37 verified, 0 partial, 3 blocked | **37/40 = 92.5%** |
| Private research gates | 7 pass, 3 blocked (EXT-01/02/03) | **7/10 = 70%** |
| Public deployment gates | 0 pass, 6 blocked | **0/6 = 0%** |
| Local operational reliability criteria | 34/34 verified | **100%** |
| Backend regression suite | 1300 OK, 1 skipped | **1300/1301 = 99.92%** |
| Frontend tests | 10 + 127 + 9 = 146 pass, 0 fail | **146/146 = 100%** |
| Live health harness | 20/20 | **100%** |
| Ingress gate validator | 3 tests OK, 6/6 gates fail closed | **100%** |

**Overall production readiness:** 37 verified acceptance items out of 40
acceptance items plus 6 public gates = **37/46 = 80.43%**. The 9 unmet criteria
are all external by definition: EXT-01, EXT-02, EXT-03 and six public-ingress
gates. EXT-03 is counted conservatively in both the acceptance and public-gate
scopes.

Local operational reliability criteria (evidence in
`docs/FINAL-VALIDATION-EVIDENCE.md`): supervisor start; dispatch; interrupted
requeue; hard-kill recovery; 32.6s lease grace; backend auto-restart;
backup-scheduler auto-restart; graceful shutdown; cold start; idempotent
bootstrap; backup sidecar; manifest; retention; interval; scratch restore; full
restore; digest/FK match; truthful backup status; S3 adapter tests; off-host
hook; cloud config validation; AES-GCM encryption; tamper detection; encrypted
restore drill; status CLI; status API roles; log secret scan; 0600 permissions;
loopback listeners; full-stack recovery drill; internal audit and dependency
scans; unprivileged login hook; licensed-data inventory; reusable ingress gate
validator.

All locally resolvable reliability work is complete and verified. See
`docs/ACCEPTANCE-46-STATUS.md` for the full 46-check table and
`docs/ACCEPTANCE-CLOSURE-EVIDENCE.md` for exact external evidence requirements. Controlled
private research remains safe to continue. Public production is **NOT READY**:
all six ingress gates and all three EXT gates require genuine external evidence.

## 11. Fresh verification pass — 2026-11-25T04:30:05Z

Re-ran all locally available checks on the current tree. Backend **1300 OK, 1
skipped**; frontend **146/146**; live health **20/20**; preflight 12/12; ingress
gates 0/6 PASS with ingress disabled; EXT audit 37/40; pip/npm audits 0
vulnerabilities; 0 secret matches; 0600 permissions; loopback-only listeners.
Latest backup verified and restored into a clean target (`restored_and_verified`,
`integrity_check=ok`); full-stack recovery drill passed with exactly-once task
requeue/completion. No failures. Blocker statuses and 37/46 = 80.43% are
unchanged because the remaining 9 criteria require external evidence.
