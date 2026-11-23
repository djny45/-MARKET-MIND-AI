# Operability hardening — failure modes found and closed

Four weaknesses were found by treating this platform as something an operator has
to run for months, not something that has to pass a test suite. Each one is a
silent failure: nothing crashes, nothing alerts, and the damage only shows up
later. Every claim below is backed by a reproduction run on this host.

Product boundary is unchanged: research only, no broker execution.

## 1. A recycled PID blocked every scheduled backup, forever

**Failure.** `DrLock` treated a lock as held whenever the recorded PID existed.
After a crash or reboot the kernel reuses PIDs; the lock then pointed at an
unrelated process and `acquire()` raised `dr_lock_held_by_pid_<pid>` on every
scheduled run. `stale_count()` — the restart-recovery path — also reported `0`,
so nothing ever cleaned it up and backups silently stopped.

**Reproduction (before the fix).**

```
lock = {"pid": 1, "created_at": "2026-01-01T00:00:00Z"}   # PID 1 is alive, it is not a backup
acquire()          -> BLOCKED FOREVER: dr_lock_held_by_pid_1
stale_count()      -> 0
```

**Fix.** Locks now record `pid_start` (from `/proc/<pid>/stat`) and `host`. A lock
is stale when its PID is dead, when the live PID's start time no longer matches
(the PID was recycled), or when it is older than a ceiling
(`MARKET_MIND_DR_LOCK_MAX_AGE`, default 24h) so a hung holder cannot block DR
indefinitely. Legacy locks without an identity keep the conservative
live-while-PID-alive behaviour, because a blocked backup is cheaper than two
concurrent ones.

**Verified.** Recycled PID → `acquired_after_stale_lock_recovery`
(`pid_reused_by_other_process`); genuine live lock → still blocked,
`stale_count() == 0`; live holder older than the ceiling →
`lock_age_exceeded`; dead PID → `pid_not_running`. Four regression tests in
`backend/tests/test_recovery_drills.py`. The full DR drill
(`run_dr_final.sh`) still completes: fingerprint `matched`, integrity `ok`,
retention keeps 2, `stale_dr_locks_removed: 1`.

## 2. Append-only research audit logs grew without bound

**Failure.** `research_shadow_log.jsonl`, `shadow_tracker_audit.jsonl`,
`skill_cadence_audit.jsonl` and `skill_promotion_audit.jsonl` were appended to
forever with no retention. They were the only artefacts on the host that could
fill the disk and take down research, backups and the API together.

**Fix.** Writes go through `app.audit_jsonl.append_record`, which rotates the
active file to `<name>.1..<name>.N` when it would pass
`MARKET_MIND_AUDIT_LOG_MAX_BYTES` (default 5 MiB, `MARKET_MIND_AUDIT_LOG_KEEP`,
default 3). Records stay on disk as evidence — nothing is deleted inside the
window. Readers use `read_records`, which spans archives oldest-first, so metrics
do not drop when a log rotates, and which skips a line truncated by a crash
instead of raising.

**Second defect found while testing this.** A crash mid-write leaves an
unterminated final line; the next append was glued onto it, corrupting both
records. The writer now emits a newline first, so the interrupted record stays
isolated and is skipped by readers while the next event is intact.

**Verified.** Rotation keeps ordering and the retention bound; other logs are
never touched; a truncated tail yields `[1]` then `[1, 3]` after the next append;
shadow metrics still report all six events across a rotated log. Twelve tests in
`backend/tests/test_audit_jsonl_rotation.py`.

## 3. `/api/ready` reported ready when it could not accept a write

**Failure.** Readiness only proved SQLite could be read. On a read-only mount or
a nearly full volume every ingest, session and audit write fails while `/api/ready`
kept returning 200 — the Docker healthcheck and any orchestrator saw a healthy
service that could not store data.

**Fix.** Readiness probes the write lock (`BEGIN IMMEDIATE` / `ROLLBACK`) and
reports storage headroom for the database volume
(`MARKET_MIND_DISK_MIN_FREE_MB`, default 512 MiB). `low` keeps the service ready
and visible; `critical` (below a quarter of the threshold) returns 503 with both
checks in the detail. The database path is still never exposed.

**Verified.** Writable probe true on a temp database; a threshold above the
available space returns 503 with `storage.status == "critical"` while the
database is still writable; `low` stays ready; a non-writable database returns
503. Four tests in `backend/tests/test_service_status.py`.

## 4. The auth session table had no cleanup path

**Failure.** `purge_expired_sessions()` existed and was unit-tested, but nothing
called it and no scheduler ran it. Every login left a row behind, so
`auth_sessions` grew for the life of the deployment.

**Fix.** `create_session` runs the purge at most once per
`MARKET_MIND_SESSION_PURGE_INTERVAL` seconds (default 3600), keeping a live host
bounded without cron while staying off the hot path. A purge failure is
swallowed: housekeeping must never turn a successful login into an error.

**Verified.** An expired session is swept by a later login; a purge inside the
interval is throttled and does not run twice. `backend/tests/test_auth_session_store.py`.

## 5. Failed logins were unlimited, and account existence leaked by timing

**Failure.** `/api/auth/login` had no per-account throttling: `RateLimitMiddleware`
is disabled unless an operator sets `API_RATE_LIMIT_PER_MINUTE`, so a default
deployment accepted unlimited guesses. Worse, an unknown username answered in
**0.0 ms** while a real account cost ~32 ms of scrypt work — a **5268x** timing
signal that tells an attacker which usernames exist before they spend a single
guess.

**Fix.** `app/login_guard.py` counts failures per account and client address in a
sliding window (`MARKET_MIND_LOGIN_MAX_FAILURES`, default 5 per 900 s) and locks
the pair out with exponential backoff (`MARKET_MIND_LOGIN_LOCKOUT_SECONDS`, default
300 s, doubling up to the window length). Blocked attempts return 429 with
`Retry-After` and are audited with `reason=login_throttled`. Unknown usernames are
throttled identically, so the response cannot be used as an oracle. `authenticate()`
now verifies a fixed dummy hash when the account is missing, equalising cost.

**Verified.** Timing after the fix: unknown **32.3 ms** vs known **32.4 ms**
(ratio 1.00x). Twelve tests in `backend/tests/test_login_throttle.py`, including
lockout, doubling cap, expiry, per-account isolation, bounded key tracking and an
end-to-end 401/401/401 → 429 sequence through the real app.

**Boundary.** Counters are in-process because the platform is single-host
(ADR-0001); a restart clears them, which cannot help an attacker.

## 6. A stopped backup schedule still reported `"status": "ok"`

**Failure.** `GET /api/backup/status` returned a constant `ok`. If the schedule
stopped — stuck lock, broken cron entry, full disk — the admin panel and any
monitor kept showing a healthy system while recovery capability decayed
silently. This is the same failure class as the recycled-PID bug in §1.

**Fix.** The endpoint now reports `freshness`: `never_run`, `stale` or `ok`, with
`newest_age_seconds` and a configurable bound
(`MARKET_MIND_BACKUP_MAX_AGE_SECONDS`, default 90000 s ≈ 25 h). Overall `status`
becomes `missing` or `stale` instead of a constant `ok`.

**Verified.** No backups → `missing`/`never_run`; fresh → `ok`; 55 h old →
`stale`; newest file wins when several exist; the threshold is validated and falls
back on bad input; no database path leaks. Seven tests in
`backend/tests/test_backup_freshness.py`.

**Deliberate limit.** Backup freshness is *not* part of `/api/ready`: a stale
backup must never take a serving API out of rotation. It belongs in monitoring,
not in the load balancer.

## Operational knobs added

| Variable | Default | Purpose |
| --- | --- | --- |
| `MARKET_MIND_DR_LOCK_MAX_AGE` | `86400` | Seconds before a held DR lock is considered stuck |
| `MARKET_MIND_AUDIT_LOG_MAX_BYTES` | `5242880` | Rotation threshold for research audit logs |
| `MARKET_MIND_AUDIT_LOG_KEEP` | `3` | Rotated audit archives retained |
| `MARKET_MIND_DISK_MIN_FREE_MB` | `512` | Readiness disk headroom threshold |
| `MARKET_MIND_SESSION_PURGE_INTERVAL` | `3600` | Minimum seconds between session purges |
| `MARKET_MIND_LOGIN_MAX_FAILURES` | `5` | Failed logins per window before lockout |
| `MARKET_MIND_LOGIN_WINDOW_SECONDS` | `900` | Sliding window for login failures |
| `MARKET_MIND_LOGIN_LOCKOUT_SECONDS` | `300` | First lockout length (doubles per offence) |
| `MARKET_MIND_BACKUP_MAX_AGE_SECONDS` | `90000` | Age at which `/api/backup/status` reports `stale` |

## Still operator-owned

Nothing here replaces host-level work: real off-host (S3) transfer, cron/systemd
installation, TLS ingress, log shipping and an independent penetration test
remain operator or infrastructure tasks.
