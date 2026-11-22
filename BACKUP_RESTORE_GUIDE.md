# BACKUP AND RESTORE GUIDE

The SQLite research database lives on the `market_mind_data` Docker volume.
`backend/backup_database.py` and `backend/restore_database.py` provide verified,
atomic operations; CI includes a backup/restore round-trip.

## What is protected

Research observations, task history, worker memory candidates, review records,
watchlists and saved workflows stored in SQLite.

## Create a verified backup

From the repository root, against a stopped or quiesced stack:

```bash
python backend/backup_database.py <backup.db> --source <path-to-market-mind.db>
```

The helper checks `PRAGMA integrity_check`, requires the `market_bars` table,
writes through a temporary file and verifies the result before replacing the
destination. It refuses to overwrite an existing backup unless `--overwrite` is
given. Do not point source and destination at the same file.

## Restore

```bash
python backend/restore_database.py <backup.db> <path-to-market-mind.db> --overwrite
```

The restore helper verifies the backup and the restored database before an
atomic replacement and leaves the target untouched on failure.

## Volume-level procedure

1. `docker compose down` (never `down -v` unless intentionally deleting data).
2. Copy the `market_mind_data` volume contents to a secure, off-host location.
3. Verify the copy and record its checksum and creation time.
4. Restore the volume, then start with `docker compose up -d`.
5. Confirm `GET /api/health` and `GET /api/ready` succeed and that task history
   and watchlists are present.

## Retention and drills

- Keep encrypted off-host copies with a documented retention period.
- Perform a host-specific restore drill before relying on this procedure; a
  CI round-trip is necessary but not sufficient for host acceptance.
- Migration rollback and incident procedures remain tracked as outstanding in
  `REMAINING_WORK.md`.

## Executed drill (2026-11-22, operator-local)

Database: `data/market_mind.db` (production schema). Target:
`/tmp/opencode/backup-drill/`.

```bash
# 1. Ensure the runtime schema exists (idempotent).
PYTHONPATH=. python3 -c "from app.market_store import _connect; _connect()"

# 2. Backup (verified).
PYTHONPATH=. python3 backend/backup_database.py \
  /tmp/opencode/backup-drill/market_mind_backup.db --source data/market_mind.db

# 3. Restore (verified).
PYTHONPATH=. python3 backend/restore_database.py \
  /tmp/opencode/backup-drill/market_mind_backup.db \
  /tmp/opencode/backup-drill/restored_market_mind.db --overwrite

# 4. Verify source vs restored: integrity + row counts per table.
```

Results (verified 2026-11-22):

- Backup: `status=verified`, `backup_integrity=ok`, `source_integrity=ok`
- Restore: `status=restored_and_verified`, `restored_integrity=ok`
- Row-count parity: `analytical_agent_tasks`, `analytical_agent_task_retries`,
  `analytical_agent_task_events`, `research_quality_evaluations`, `workflows`,
  `analytical_agent_supervisor_lease`, `analytical_agent_supervisor_metrics` all
  match between source and restored; `PRAGMA integrity_check` returns `ok`.
- The source and restored files' SHA-256 differ because the source file is
  recreated after each run (the drill was performed on a schema-initialized
  DB; equivalence was verified by row-count and integrity parity).

## Safety

Backups may contain research notes and operator feedback. Treat them as
sensitive; never commit them or place them in the frontend/public directories.
