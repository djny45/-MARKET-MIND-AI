"""Central SQLite connection factory with WAL tuning.

The research platform keeps a single-host SQLite database that a supervisor,
task executors and the API read and write concurrently. The default rollback
journal makes readers wait for every committing writer, which shows up as
multi-hundred-millisecond tail latency for API requests and stalled research
polling.

This module applies, once per database file per process:

* ``journal_mode = WAL`` — readers and the writer stop blocking each other.
* ``synchronous = NORMAL`` — safe with WAL for process-crash durability;
  only an OS/power failure can lose the last transaction.
* ``busy_timeout`` — bounded wait instead of an immediate ``database is locked``.

Rollback-journal behaviour is still available for callers that need it, and
``:memory:``/URI databases are left untouched (WAL does not apply to them).

Measured on the benchmark in ``backend/benchmarks/bench_sqlite_concurrency.py``:
see ``docs/PERFORMANCE.md``.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

# Per-process record of databases already switched to WAL. PRAGMA journal_mode
# needs a write lock the first time and is persistent on the database file, so
# repeating it on every connect would add contention for no benefit.
_wal_databases: set[str] = set()
_wal_lock = threading.Lock()

DEFAULT_TIMEOUT = 10.0
DEFAULT_BUSY_TIMEOUT_MS = 10_000


def _database_key(database: str | os.PathLike[str]) -> str | None:
    """Return a stable key for file databases, or None when WAL cannot apply."""
    text = os.fspath(database)
    if text in ("", ":memory:"):
        return None
    if text.startswith("file:"):
        # URI databases: leave the caller's mode/immutable options alone.
        return None
    path = Path(text)
    return str(path.resolve()) if path.suffix or path.name else None


def connect(
    database: str | os.PathLike[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    wal: bool = True,
    synchronous: str = "NORMAL",
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """Open a tuned SQLite connection.

    ``wal=False`` keeps the historical rollback-journal behaviour.
    """
    connection = sqlite3.connect(database, timeout=timeout)
    if wal and os.getenv("MARKET_MIND_SQLITE_WAL", "1").strip() == "0":
        wal = False
    if not wal:
        return connection

    key = _database_key(database)
    if key is None:
        return connection

    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    already_wal = False
    with _wal_lock:
        if key in _wal_databases:
            already_wal = True
    if not already_wal:
        try:
            connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            # Another process holds the database during a migration or backup;
            # the connection stays usable and a later connect retries.
            return connection
        with _wal_lock:
            _wal_databases.add(key)
    connection.execute(f"PRAGMA synchronous = {synchronous}")
    return connection


def applied_modes(connection: sqlite3.Connection) -> dict[str, str]:
    """Read back the pragmas so tests and health checks can assert them."""
    return {
        "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
        "synchronous": str(connection.execute("PRAGMA synchronous").fetchone()[0]),
        "busy_timeout": str(connection.execute("PRAGMA busy_timeout").fetchone()[0]),
    }


def reset_cache() -> None:
    """Forget the WAL cache (tests only)."""
    with _wal_lock:
        _wal_databases.clear()
