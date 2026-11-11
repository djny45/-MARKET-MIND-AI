"""SQLite-backed opaque session persistence primitives.

The caller must hash bearer and CSRF tokens before passing them here. This
module deliberately does not issue cookies, authenticate HTTP requests, or
protect FastAPI routes; those controls belong to the integration layer.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_sessions (
    session_token_hash TEXT PRIMARY KEY,
    csrf_token_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    idle_expires_at INTEGER NOT NULL,
    absolute_expires_at INTEGER NOT NULL,
    revoked_at INTEGER,
    CHECK (created_at <= last_seen_at),
    CHECK (last_seen_at <= absolute_expires_at),
    CHECK (idle_expires_at <= absolute_expires_at),
    CHECK (absolute_expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry
    ON auth_sessions(idle_expires_at, absolute_expires_at);
"""


def _validate_digest(value: str, label: str) -> None:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")


def _positive_int(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _connect(database_path: str | Path) -> sqlite3.Connection:
    if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
        raise ValueError("database_path must be a non-empty path")
    connection = sqlite3.connect(str(database_path), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def _session_connection(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Commit successful operations and always close the SQLite connection."""
    connection = _connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_auth_store(database_path: str | Path) -> None:
    """Create the session schema and restrict the database file on POSIX."""
    if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
        raise ValueError("database_path must be a non-empty path")
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _session_connection(path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(_SCHEMA)
    try:
        path.chmod(0o600)
    except OSError:
        # Filesystems without POSIX permission support need deployment-level
        # access controls; initialization should not hide that operational fact.
        pass


def create_session(
    database_path: str | Path,
    session_token_hash: str,
    csrf_token_hash: str,
    *,
    now: int,
    idle_ttl_seconds: int,
    absolute_ttl_seconds: int,
) -> dict[str, int]:
    """Persist only token digests and return the session expiry metadata."""
    _validate_digest(session_token_hash, "session_token_hash")
    _validate_digest(csrf_token_hash, "csrf_token_hash")
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("now must be a non-negative integer")
    idle_ttl = _positive_int(idle_ttl_seconds, "idle_ttl_seconds")
    absolute_ttl = _positive_int(absolute_ttl_seconds, "absolute_ttl_seconds")
    if idle_ttl > absolute_ttl:
        idle_ttl = absolute_ttl

    absolute_expires_at = now + absolute_ttl
    idle_expires_at = min(now + idle_ttl, absolute_expires_at)
    with _session_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO auth_sessions (
                session_token_hash, csrf_token_hash, created_at, last_seen_at,
                idle_expires_at, absolute_expires_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                session_token_hash,
                csrf_token_hash,
                now,
                now,
                idle_expires_at,
                absolute_expires_at,
            ),
        )
    return {
        "created_at": now,
        "last_seen_at": now,
        "idle_expires_at": idle_expires_at,
        "absolute_expires_at": absolute_expires_at,
    }


def get_session(
    database_path: str | Path,
    session_token_hash: str,
    *,
    now: int,
    idle_ttl_seconds: int,
) -> dict[str, Any] | None:
    """Load an active session and atomically slide its idle expiry."""
    _validate_digest(session_token_hash, "session_token_hash")
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("now must be a non-negative integer")
    idle_ttl = _positive_int(idle_ttl_seconds, "idle_ttl_seconds")

    with _connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT csrf_token_hash, created_at, last_seen_at,
                   idle_expires_at, absolute_expires_at, revoked_at
            FROM auth_sessions WHERE session_token_hash = ?
            """,
            (session_token_hash,),
        ).fetchone()
        if row is None or row["revoked_at"] is not None:
            connection.commit()
            return None
        effective_now = max(now, row["last_seen_at"])
        if effective_now >= row["idle_expires_at"] or effective_now >= row["absolute_expires_at"]:
            connection.execute(
                """
                UPDATE auth_sessions SET revoked_at = ?
                WHERE session_token_hash = ? AND revoked_at IS NULL
                """,
                (effective_now, session_token_hash),
            )
            connection.commit()
            return None

        next_idle_expiry = min(effective_now + idle_ttl, row["absolute_expires_at"])
        connection.execute(
            """
            UPDATE auth_sessions
            SET last_seen_at = ?, idle_expires_at = ?
            WHERE session_token_hash = ? AND revoked_at IS NULL
            """,
            (effective_now, next_idle_expiry, session_token_hash),
        )
        connection.commit()
        return {
            "csrf_token_hash": row["csrf_token_hash"],
            "created_at": row["created_at"],
            "last_seen_at": effective_now,
            "idle_expires_at": next_idle_expiry,
            "absolute_expires_at": row["absolute_expires_at"],
        }


def revoke_session(
    database_path: str | Path,
    session_token_hash: str,
    *,
    now: int,
) -> bool:
    """Revoke a session once; return whether an active row was changed."""
    _validate_digest(session_token_hash, "session_token_hash")
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("now must be a non-negative integer")
    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE auth_sessions SET revoked_at = ?
            WHERE session_token_hash = ? AND revoked_at IS NULL
            """,
            (now, session_token_hash),
        )
        return cursor.rowcount == 1


def purge_expired_sessions(database_path: str | Path, *, now: int) -> int:
    """Delete revoked and expired session rows; return the number removed."""
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("now must be a non-negative integer")
    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM auth_sessions
            WHERE revoked_at IS NOT NULL
               OR idle_expires_at <= ?
               OR absolute_expires_at <= ?
            """,
            (now, now),
        )
        return cursor.rowcount
