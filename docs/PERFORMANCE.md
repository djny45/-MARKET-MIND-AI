# Performance — measured, not asserted

Research-only platform. Nothing here changes the product boundary: no live
broker execution, wallet keys, transaction signing or order routing.

## 1. Storage: WAL instead of the rollback journal

Every SQLite connection in `backend/app` now goes through
`backend/app/sqlite_tuning.py`, which applies:

| Pragma | Value | Why |
| --- | --- | --- |
| `journal_mode` | `WAL` | readers stop waiting for the committing writer |
| `synchronous` | `NORMAL` | durable across process crashes with WAL; only an OS/power failure can lose the last transaction |
| `busy_timeout` | 10 000 ms (5 000 ms for session store) | bounded wait instead of an immediate `database is locked` |

`PRAGMA journal_mode` needs a write lock the first time and is persistent on the
database file, so it is applied once per file per process; `synchronous` and
`busy_timeout` are per connection and applied every time. `:memory:` and `file:`
URI databases are left untouched. Set `MARKET_MIND_SQLITE_WAL=0` to fall back to
the previous rollback-journal behaviour (rollback switch, kept for operators
who need it during an incident).

Why this matters: the platform runs one supervisor, several task executors and
the HTTP API against a single SQLite file. With the rollback journal, every
commit blocks readers, which appears as multi-second request stalls rather than
a lower average.

## 2. Measurement

### 2.1 Real HTTP path, with concurrent writes

`backend/benchmarks/bench_http_latency.py` seeds 20 000 bars into a temporary
database, starts the real FastAPI app in a subprocess, runs 400 write commits
from a second thread and probes
`/api/market-data/lineage?symbol=BENCH00&interval=1d&limit=200` 400 times at
concurrency 8 through `scripts/load_check.py`. Both modes do the same write
attempts (400) and the same reads (400).

Run: `PYTHONPATH=backend python -m backend.benchmarks.bench_http_latency`

| Mode | Requests/s | p50 | p95 | max |
| --- | --- | --- | --- | --- |
| rollback_journal | 156.8 | 12.5 ms | **310.6 ms** | **1545.4 ms** |
| WAL (`synchronous=NORMAL`) | **436.1** | 14.3 ms | **39.0 ms** | **102.4 ms** |

**p95 8.0× lower, worst case 15.1× lower, 2.8× the throughput**, with the same
number of successful writes and a 0.0 error rate in both runs. The p50 is
unchanged — this fixes stalls, not the fast path, which is exactly what an
operator feels as a "slow" application.

### 2.2 Storage-only contention microbenchmark

`backend/benchmarks/bench_sqlite_concurrency.py` (4 readers + 1 writer, 600
reads, 60 batches):

| Mode | Reads/s | read max |
| --- | --- | --- |
| rollback_journal | 1 721.7 | 329.2 ms |
| WAL | 13 073.6 | 0.763 ms |

## 3. Safety checks that accompany the change
- `backend/tests/test_sqlite_tuning.py` asserts the pragmas are applied, that a
  reset cache still finds a persisted WAL database, that `:memory:` is
  unaffected, that `wal=False` still works, that committed rows survive reopen,
  that the **online backup API captures rows still sitting in the WAL**
  (`backend/backup_database.py` uses `Connection.backup`, which is WAL-safe),
  and that no application module opens a file database behind the factory.
- `docs/RECOVERY_DRILL_EVIDENCE.md` drills are re-run after the change so
  backup/restore parity is proven on a WAL database.
- `.gitignore` covers `*.db-wal`, `*.db-shm` and `*.db-journal`.

### 3.1 Defect this change exposed, and its fix

Copying a WAL-mode database with `Connection.backup` switches the *copy* to WAL
mode. `backend/backup_database.py` and `backend/restore_database.py` then moved
only the `.db` file into place, so every backup and every restore left orphaned
`<name>.<random>.tmp-shm` (32 KB) and `.tmp-wal` files in the DR directory. The
old `with sqlite3.connect(...)` blocks never closed the connection, so the copy
depended on garbage collection to checkpoint.

Reproduced before the fix: one backup + one restore left four orphan files
(`market_mind.db.qwn2wf3q.restore.tmp-shm`, `…restore.tmp-wal`,
`backup.db.zynsjjb1.tmp-shm`, `…tmp-wal`). Retention only prunes `*.db`,
`*.sha256` and `*.json`, so those files would accumulate forever at ~32 KB per
run and be swept into any off-host upload of the backup directory.

Fix:

- connections are closed explicitly, and the copy is returned to the rollback
  journal (`PRAGMA journal_mode=DELETE`) before the artifact is moved, so the
  backup is one self-contained file whose SHA-256 covers all of its rows;
- `<name>-wal`, `<name>-shm`, `<name>-journal` are removed next to the finished
  backup/restore target, and temporary sidecars are removed in `finally`;
- `scripts/backup_orchestrator.py` retention now also sweeps orphans
  (`*.db-wal`, `*.db-shm`, `*.db-journal`, `*.tmp*`) and reports
  `orphans_removed`, so already-polluted directories heal on the next run
  (dry runs report without deleting).

Regression tests: `backend/tests/test_backup_wal_hygiene.py` (4 tests: a live
WAL source yields a single-file backup, the file alone holds every row, a stale
WAL next to a restore target is replaced, no temporary sidecars survive) and
two retention sweep tests in `backend/tests/test_recovery_drills.py`. The DR
drill now leaves exactly `db + json + sha256` in the backup directory.

## 4. What was deliberately not done

- No caching layer, no new dependency, no query rewriting: no measurement
  justified it yet, and the project's dependency audit is clean today.
- No multi-host queue: SQLite remains single-host with one supervisor
  (ADR-0001 is still design-only).
- No WAL checkpoint tuning (`wal_autocheckpoint` stays at the SQLite default)
  until a long-run workload shows a need.
