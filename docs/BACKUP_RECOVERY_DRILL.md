# Backup / Recovery Drill — executed 2026-11-22

Research-only platform. No live trading, wallet keys, signing or order routing
was enabled, configured or exercised at any point in this drill.

## Scope and environment

- Repository: `/tmp/opencode/MARKET-MIND-AI-target` (branch `main`, unchanged).
- Drill root (temporary, outside the repository):
  `/tmp/opencode/market-mind-dr-drill-20261122`
- Unabridged raw log (480 lines):
  `/tmp/opencode/market-mind-dr-drill-20261122/drill.log`
- Runner script (commands only): `/tmp/opencode/run_dr_drill.sh`
- `PYTHONPATH=.:./backend`, Python 3.11.6, `trivy`/`docker` not used in this drill.
- The repository's untracked runtime DB (`data/market_mind.db`) currently has
  task tables but **no `market_bars` table**, which the verified backup helper
  requires. To avoid mutating repository state, the drill source was a brand-new
  DB initialized with the repository's own schema (`app.market_store._connect`
  and `app.analytical_agent_tasks._connect`) plus one synthetic bar and one
  stale `running` task. Fixture helper: `/tmp/opencode/dr-drill-fixture.py`.

## Result summary (honest status per step)

| # | Step | Status |
|---|------|--------|
| 1 | Initialize clean research DB with repo schema | **FAIL** on first attempt (fixture bug), then **PASS** after fix — see "Corrected defect" |
| 2 | Effective scheduler configuration, no secrets printed | **PASS** |
| 3 | Verified backup via `scripts/backup_orchestrator.py run` | **PASS** |
| 4 | SHA-256 sidecar vs independent `sha256sum` | **PASS** |
| 5 | Backup manifest with integrity + per-table counts | **PASS** |
| 6 | Orchestrator `status` | **PASS** |
| 7 | Non-destructive `verify` (scratch restore) | **PASS** |
| 8 | Restore into a brand-new clean directory | **PASS** |
| 9 | Source vs restored integrity / row-count parity | **PASS** |
| 10 | Retention pruning (keep newest 2, sidecars removed) | **PASS** |
| 11 | Off-host storage hook via operator command | **PASS** (local copy target) |
| 12 | Interrupted run refusal, then explicit `resume` | **PASS** |
| 13 | Post-restart recovery: stale lock + interrupted task | **PASS** |
| 14 | Migration rollback (arm → simulate failure → rollback) | **PASS** |
| 15 | Incident alerting: disabled and local webhook delivery | **PASS** |
| 16 | Cron / systemd hook generation (no installation) | **PASS** (generation only) |
| 17 | Install cron/systemd timer on host | **BLOCKED** — no host init access in this container; operator action required |
| 18 | Docker named-volume (`market_mind_data`) restore | **BLOCKED** — `docker` binary absent locally |
| 19 | Real S3-compatible off-host target | **BLOCKED** — no endpoint or credentials exist; hook interface exercised with a local copy target instead |
| 20 | Migration against a real application migration runner | **BLOCKED** — repo has only a `schema_migrations` version table, no migration CLI; simulated failure used |

### Corrected defect (do not fabricate a clean first run)

The first drill attempt failed at step 1 because the temporary fixture called the
application's task `_connect` (a `@contextmanager`) as a plain function:

```
$ python3 /tmp/opencode/dr-drill-fixture.py .../source/market_mind.db
Traceback (most recent call last):
  File "/tmp/opencode/dr-drill-fixture.py", line 17, in <module>
    task_connect().close()
AttributeError: '_GeneratorContextManager' object has no attribute 'close'
[exit=1]
```

The fixture was corrected to `with task_connect() as ...`, and the **entire drill
was re-run from an empty directory**. Everything below is from that final run.
The first-attempt log was retained at `/tmp/opencode/dr-drill-attempt1.log`.
A second correction was made to the step-14 verification command: after a
successful rollback the simulated `migration_marker` table is absent (that is
the expected pre-migration state), so the check now asserts absence via
`sqlite_master` rather than querying the table directly.

Expected non-zero exits that are **not** failures: step 12 first command
`[exit=1]` (interrupted run correctly refused), step 13 final `ls *.lock`
`[exit=2]` (no lock files remain), step 15 failing backup `[exit=1]` (used to
trigger the alert hook).

---

## Evidence — exact commands and output

Commands below are quoted exactly as logged. Long outputs are reproduced
verbatim where they carry evidence; the full log holds everything including
intermediate `status` and `ls` listings.

### Step 1 — clean source DB (PASS after fix)

```
$ python3 /tmp/opencode/dr-drill-fixture.py /tmp/opencode/market-mind-dr-drill-20261122/source/market_mind.db
{
  "database": "/tmp/opencode/market-mind-dr-drill-20261122/source/market_mind.db",
  "row_counts": {
    "analytical_agent_tasks": 1,
    "market_bars": 1
  },
  "tables": [
    "analytical_agent_supervisor_heartbeat",
    "analytical_agent_task_events",
    "analytical_agent_task_retries",
    "analytical_agent_tasks",
    "audit_events",
    "market_bars",
    "research_quality_evaluations",
    "schema_migrations"
  ]
}
[exit=0]
```

### Step 2 — scheduler configuration (PASS)

```
$ python3 scripts/backup_scheduler.py config
{
  "status": "ok",
  "source": "./data/market_mind.db",
  "backup_dir": "./data/backups",
  "retention_days": "30",
  "retention_count": "",
  "upload_hook_configured": false,
  "incident_webhook_configured": false,
  "state_dir": "./data/backups/.state",
  "timeout_seconds": 300,
  "note": "Values only; URLs and command strings are never printed."
}
[exit=0]
```

### Step 3 — verified backup (PASS)

```
$ python3 scripts/backup_orchestrator.py run --source /tmp/opencode/market-mind-dr-drill-20261122/source/market_mind.db --destination-dir /tmp/opencode/market-mind-dr-drill-20261122/backups --state-dir /tmp/opencode/market-mind-dr-drill-20261122/state --retention-days 7 --retention-count 5
{
  "status": "completed",
  "backup": "/tmp/opencode/market-mind-dr-drill-20261122/backups/market_mind-20261122T183203Z.db",
  "sha256": "dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3",
  "upload": null,
  "retention": {
    "status": "completed",
    "candidates": 1,
    "retained": 1,
    "pruned": [],
    "retention_days": 7,
    "retention_count": 5
  }
}
[exit=0]
```

### Step 4 — SHA-256 sidecar (PASS)

```
$ cat .../market_mind-20261122T183203Z.db.sha256
dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3  market_mind-20261122T183203Z.db
[exit=0]
$ sha256sum .../market_mind-20261122T183203Z.db
dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3  /tmp/opencode/market-mind-dr-drill-20261122/backups/market_mind-20261122T183203Z.db
[exit=0]
```

### Step 5 — manifest (PASS)

```
$ cat .../market_mind-20261122T183203Z.db.json
{
  "backup": "market_mind-20261122T183203Z.db",
  "bytes": 86016,
  "created_at": "2026-11-22T18:32:03.478470Z",
  "fingerprint": {
    "bytes": 86016,
    "integrity": "ok",
    "schema_version": 0,
    "table_counts": {
      "analytical_agent_supervisor_heartbeat": 0,
      "analytical_agent_task_events": 0,
      "analytical_agent_task_retries": 0,
      "analytical_agent_tasks": 1,
      "audit_events": 0,
      "market_bars": 1,
      "research_quality_evaluations": 0,
      "schema_migrations": 0
    }
  },
  "integrity": "ok",
  "kind": "market_mind_backup",
  "retention_count": 5,
  "retention_days": 7,
  "sha256": "dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3",
  "source": "/tmp/opencode/market-mind-dr-drill-20261122/source/market_mind.db",
  "upload": { "status": "not_configured" },
  "version": 1
}
[exit=0]
```

### Step 6 — status (PASS)

```
$ python3 scripts/backup_orchestrator.py status --destination-dir .../backups --state-dir .../state
{
  "status": "ok",
  "backups": [
    {
      "backup": "market_mind-20261122T183203Z.db",
      "bytes": 86016,
      "checksum": "verified",
      "manifest_status": "market_mind_backup",
      "upload": "not_configured",
      "created_at": "2026-11-22T18:32:03.478470Z"
    }
  ],
  "journal": {
    "backup": "market_mind-20261122T183203Z.db",
    "phase": "completed",
    "status": "completed",
    "resumable": true,
    "sha256": "dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3"
  }
}
[exit=0]
```

(Fields repeated verbatim in the raw log; the excerpt above removes only
duplicate `destination` / `retention` lines for readability — none were changed.)

### Step 7 — non-destructive verify (PASS)

```
$ python3 scripts/restore_orchestrator.py verify --backup .../market_mind-20261122T183203Z.db --state-dir .../state
{
  "status": "verified",
  "restore_script": "restored_and_verified",
  "fingerprint": { "integrity": "ok", "schema_version": 0, "bytes": 86016,
    "table_counts": { "analytical_agent_tasks": 1, "market_bars": 1, "...": 0 } },
  "comparison": {
    "status": "matched", "compared": true, "row_count_differences": {},
    "schema_version_backup": 0, "schema_version_restored": 0, "schema_version_match": true
  }
}
[exit=0]
```

(Only the repeated per-table zero counts were collapsed in this excerpt; the
full output is in the raw log.)

### Step 8 — restore into a clean directory (PASS)

```
$ python3 scripts/restore_orchestrator.py restore --backup .../market_mind-20261122T183203Z.db --target .../clean-host/data --state-dir .../state
{
  "status": "restored_and_verified",
  "destination": "/tmp/opencode/market-mind-dr-drill-20261122/clean-host/data/market_mind.db",
  "sha256": "dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3",
  "restore_script": "restored_and_verified",
  "fingerprint": { "integrity": "ok", "schema_version": 0, "bytes": 86016,
    "table_counts": { "analytical_agent_tasks": 1, "market_bars": 1 } },
  "comparison": { "status": "matched", "compared": true,
    "row_count_differences": {}, "schema_version_match": true },
  "restored_at": "2026-11-22T18:32:03.810426Z"
}
[exit=0]
```

### Step 9 — parity (PASS)

```
$ python3 -c "import sys,json; sys.path.insert(0,'scripts'); from dr_common import database_fingerprint as f; ..."
{
  "parity": true,
  "restored": { "bytes": 86016, "integrity": "ok", "schema_version": 0,
    "table_counts": { "analytical_agent_tasks": 1, "market_bars": 1, "...": 0 } },
  "source": { "bytes": 86016, "integrity": "ok", "schema_version": 0,
    "table_counts": { "analytical_agent_tasks": 1, "market_bars": 1, "...": 0 } }
}
[exit=0]
```

`parity: true` means all per-table row counts match, both `PRAGMA
integrity_check` results are `ok`, and `schema_migrations` versions match.

### Step 10 — retention (PASS)

```
$ python3 scripts/backup_orchestrator.py prune --destination-dir .../retention --state-dir .../retention/.state --retention-days 0 --retention-count 2
{
  "status": "completed",
  "candidates": 4,
  "retained": 2,
  "pruned": [
    "market_mind-20260102T000000Z.db",
    "market_mind-20260101T000000Z.db"
  ],
  "retention_days": 0,
  "retention_count": 2
}
[exit=0]
```

The post-prune `ls -1` showed only `market_mind-20260103T000000Z.db` and
`market_mind-20260104T000000Z.db` with their `.sha256` and `.json` sidecars.

### Step 11 — off-host hook (PASS, local target)

```
$ python3 scripts/backup_orchestrator.py run ... --upload-command "python3 /tmp/opencode/dr-drill-upload.py {backup} .../offhost"
{
  "status": "completed",
  "backup": ".../backups/market_mind-20261122T183204Z.db",
  "sha256": "dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3",
  "upload": {
    "status": "uploaded", "returncode": 0, "error_type": null,
    "stdout": "copied .../market_mind-20261122T183204Z.db -> .../offhost",
    "stderr": ""
  },
  "retention": { "status": "completed", "candidates": 2, "retained": 2, "pruned": [] }
}
[exit=0]
$ ls -l .../offhost
-rw------- 1 jovyan users 86016 Nov 22 18:32 market_mind-20261122T183204Z.db
[exit=0]
```

The exact command was logged with shell-escaped arguments; see `drill.log`
line 306. `{backup}`, `{sha256}`, `{name}` and `{destination}` are substituted
into an operator-supplied argv (no shell), so secrets must come from the
environment and are never embedded in the command.

### Step 12 — interrupted-task recovery (PASS)

```
$ python3 scripts/backup_orchestrator.py run ... --state-dir .../interrupted-state
{
  "status": "failed",
  "error_type": "DrInterrupted",
  "error": "incomplete_backup_run_use_resume",
  "alert": { "status": "disabled", "event": "backup_failed" }
}
[exit=1]
$ python3 scripts/backup_orchestrator.py resume ... --state-dir .../interrupted-state
{
  "status": "completed",
  "backup": ".../backups/market_mind-20260101T000000Z.db",
  "sha256": "dae39694381d3cf33a23d7d58f465026f85c710be1cbba1f500fa930209505d3",
  "upload": null,
  "retention": { "status": "completed", "candidates": 3, "retained": 3, "pruned": [] }
}
[exit=0]
```

### Step 13 — service restart recovery (PASS)

```
$ python3 scripts/service_restart_recovery.py run --db .../source/market_mind.db --state-dir .../state --stale-after-seconds 900
{
  "status": "recovered",
  "stale_dr_locks_removed": 1,
  "database_integrity": { "status": "ok", "integrity": "ok", "table_count": 9, "supervisor_heartbeat": null },
  "interrupted_task_recovery": {
    "status": "ok",
    "recovery": {
      "requeued_interrupted_count": 1,
      "queued_task_ids": [ "drill-task-1" ],
      "still_running_count": 0,
      "stale_after_seconds": 900,
      "recovery_mode": "manual_stale_requeue_no_dispatch"
    }
  },
  "mode": "explicit_requeue_no_dispatch"
}
[exit=0]
$ ls -1 .../state/*.lock
ls: cannot access '.../state/*.lock': No such file or directory
[exit=2]
```

The stale lock was removed; the app's own `recover_interrupted_research_tasks`
requeued exactly one stale `running` task without dispatching it.

### Step 14 — migration rollback (PASS)

```
$ python3 scripts/migration_rollback.py prepare --target .../source/market_mind.db --state-dir .../rollback
{ "status": "armed",
  "backup": ".../rollback/migration-backups/market_mind-20261122T183204Z.db",
  "sha256": "ca67c78d07e3037d00aeffa8906b24a94cc33a605cf3a89d742c037b1e16b0cb" }
[exit=0]
$ python3 scripts/migration_rollback.py rollback --force --target .../source/market_mind.db --state-dir .../rollback
{
  "status": "rolled_back",
  "restored_from": ".../rollback/migration-backups/market_mind-20261122T183204Z.db",
  "sha256": "ca67c78d07e3037d00aeffa8906b24a94cc33a605cf3a89d742c037b1e16b0cb",
  "failed_migration_snapshot": ".../rollback/failed-migration-20261122T183204Z.db"
}
[exit=0]
$ python3 -c "... SELECT COUNT(*) FROM sqlite_master WHERE name='migration_marker' ..."
migration_marker table present: 0
integrity: ok
[exit=0]
```

A simulated failed migration created a `migration_marker` table/row after the
snapshot; after rollback that table is absent (pre-migration state), integrity
is `ok`, and the failed state was preserved as a timestamped snapshot.

### Step 15 — incident alerting (PASS)

```
$ env -u MARKET_MIND_INCIDENT_WEBHOOK_URL python3 scripts/backup_scheduler.py config
{ ... "incident_webhook_configured": false ... }
[exit=0]
$ env MARKET_MIND_INCIDENT_WEBHOOK_URL=http://127.0.0.1:37657/hook python3 scripts/backup_orchestrator.py run --source .../missing-source.db ...
{
  "status": "failed",
  "error_type": "DrError",
  "error": "source_database_not_found:/tmp/opencode/market-mind-dr-drill-20261122/missing-source.db",
  "alert": { "status": "sent", "event": "backup_failed" }
}
[exit=1]
$ cat .../webhook-body.json
{"source": "market-mind-dr", "mode": "research-only", "event": "backup_failed", "status": "failed", "timestamp": "2026-11-22T18:32:05.089135Z", "detail": {"error_type": "DrError", "reason": "source_database_not_found:/tmp/opencode/market-mind-dr-drill-20261122/missing-source.db"}}
[exit=0]
```

The webhook receiver was a local Python `HTTPServer` bound to an ephemeral
loopback port. The delivered JSON contains no secret fields (whitelisted keys
only). With no webhook configured, alerting is a no-op (`status=disabled`).

### Step 16 — scheduling hooks (PASS; generation only)

```
$ python3 scripts/backup_scheduler.py cron-line --schedule '0 2 * * *' --log-path /var/log/market-mind-backup.log
{
  "status": "ok",
  "schedule": "0 2 * * *",
  "line": "0 2 * * * cd /tmp/opencode/MARKET-MIND-AI-target && /opt/conda/bin/python3 /tmp/opencode/MARKET-MIND-AI-target/scripts/backup_scheduler.py run >> /var/log/market-mind-backup.log 2>&1",
  "note": "Install with crontab -e; keep secrets in the service environment."
}
[exit=0]
$ python3 scripts/backup_scheduler.py systemd --interval-hours 24
{
  "status": "ok",
  "service": "[Unit]\nDescription=MARKET-MIND verified research database backup\nAfter=network-online.target\n\n[Service]\nType=oneshot\nWorkingDirectory=/tmp/opencode/MARKET-MIND-AI-target\nExecStart=/opt/conda/bin/python3 /tmp/opencode/MARKET-MIND-AI-target/scripts/backup_scheduler.py run\n# Supply MARKET_MIND_DB / MARKET_MIND_BACKUP_DIR / retention / webhook\n# via EnvironmentFile= with 0600 permissions (never inline secrets).\n",
  "timer": "[Unit]\nDescription=Daily MARKET-MIND research database backup\n\n[Timer]\nOnUnitActiveSec=24h\nPersistent=true\nUnit=market-mind-backup.service\n\n[Install]\nWantedBy=timers.target\n",
  "interval_hours": 24
}
[exit=0]
```

Nothing was installed into the host's cron or systemd.

---

## Configuration reference (all via environment; no secrets in code)

| Variable | Purpose |
|----------|---------|
| `MARKET_MIND_DB` | Source SQLite DB (default `./data/market_mind.db`) |
| `MARKET_MIND_BACKUP_DIR` | Backup destination directory (default `./data/backups`) |
| `MARKET_MIND_DR_STATE_DIR` | Journal / lock / report directory |
| `MARKET_MIND_BACKUP_RETENTION_DAYS` | Age-based retention; `0` disables age pruning |
| `MARKET_MIND_BACKUP_KEEP` | Count-based retention (newest N) |
| `MARKET_MIND_BACKUP_UPLOAD_CMD` | Off-host hook argv template: `{backup} {sha256} {name} {destination}` |
| `MARKET_MIND_INCIDENT_WEBHOOK_URL` | HTTP(S) incident webhook; unset disables alerting |
| `MARKET_MIND_DR_ALERT_ON_SUCCESS` | Optional success alerts (default false) |
| `MARKET_MIND_DR_TIMEOUT_SECONDS` | Script/hook timeout (default 300) |
| `MARKET_MIND_RECOVERY_STALE_SECONDS` | Stale-task grace period for restart recovery |

## Test evidence

```
$ PYTHONPATH=.:./backend python3 -m unittest backend.tests.test_backup_database backend.tests.test_recovery_drills -q
Ran 19 tests in 1.499s
OK

$ PYTHONPATH=.:./backend python3 -m unittest discover -s backend/tests -q
Ran 1009 tests in 88.426s
OK
```

Note: the task brief stated a 987-test baseline; the current checkout reports
1009 tests after these additions (other agents may have added tests to the same
working tree). No tests were skipped or bypassed.

## Files changed for this work

- `scripts/dr_common.py`, `scripts/backup_orchestrator.py`,
  `scripts/restore_orchestrator.py`, `scripts/migration_rollback.py`,
  `scripts/service_restart_recovery.py`, `scripts/backup_scheduler.py` (new)
- `backend/backup_database.py` (URI escaping fix for source/integrity paths)
- `backend/tests/test_backup_database.py`, `backend/tests/test_recovery_drills.py`
- `docs/BACKUP_RECOVERY_DRILL.md`, `docs/TRIVY_CI_AUDIT.md`

No workflow files, status reports, or other agents' files were modified.
