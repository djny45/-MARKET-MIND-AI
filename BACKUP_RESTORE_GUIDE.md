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

## Safety

Backups may contain research notes and operator feedback. Treat them as
sensitive; never commit them or place them in the frontend/public directories.
