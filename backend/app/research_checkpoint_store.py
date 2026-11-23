"""Content-addressed SQLite checkpoints for resumable research workflows.

Snapshots preserve caller-supplied JSON state only. They do not execute tasks,
restore external side effects, or provide distributed queue semantics.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from . import sqlite_tuning


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint payload must contain finite JSON-compatible values") from exc


class ResearchCheckpointStore:
    """Append-only, revisioned checkpoints backed by a local SQLite database."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_connection = (
            sqlite_tuning.connect(":memory:", timeout=10)
            if self.database_path == ":memory:" else None
        )
        self._closed = False
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS research_checkpoints (
                    task_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    checkpoint_id TEXT NOT NULL UNIQUE,
                    parent_checkpoint_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(task_id, revision)
                )
            """)

    def close(self) -> None:
        if self._closed:
            return
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None
        self._closed = True

    def __enter__(self) -> "ResearchCheckpointStore":
        if self._closed:
            raise RuntimeError("checkpoint store is closed")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def _connect(self):
        if self._closed:
            raise RuntimeError("checkpoint store is closed")
        from contextlib import contextmanager

        @contextmanager
        def connection_scope():
            db = self._memory_connection
            owns_connection = db is None
            if owns_connection:
                db = sqlite_tuning.connect(self.database_path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                if owns_connection:
                    db.close()
        return connection_scope()

    @staticmethod
    def _checkpoint_id(task_id: str, revision: int, parent_id: str | None, payload_json: str) -> str:
        envelope = _canonical_json({
            "task_id": task_id,
            "revision": revision,
            "parent_checkpoint_id": parent_id,
            "payload": json.loads(payload_json),
        })
        return hashlib.sha256(envelope.encode("utf-8")).hexdigest()

    def save(
        self, task_id: str, payload: dict[str, Any],
        expected_revision: int = 0,
    ) -> dict[str, Any]:
        """Append one checkpoint if expected_revision matches the current head.

        Use expected_revision=0 for the first snapshot, then pass the returned
        revision for the next write. Concurrent writers cannot silently fork.
        """
        if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
            raise ValueError("task_id must contain 1 to 200 characters")
        if not isinstance(payload, dict):
            raise ValueError("checkpoint payload must be an object")
        if (isinstance(expected_revision, bool) or not isinstance(expected_revision, int)
                or expected_revision < 0):
            raise ValueError("expected_revision must be a non-negative integer")
        payload_json = _canonical_json(payload)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            head = db.execute(
                "SELECT revision,checkpoint_id FROM research_checkpoints "
                "WHERE task_id=? ORDER BY revision DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            current_revision = head["revision"] if head else 0
            if current_revision != expected_revision:
                raise ValueError("checkpoint revision conflict")
            revision = current_revision + 1
            parent_id = head["checkpoint_id"] if head else None
            checkpoint_id = self._checkpoint_id(task_id, revision, parent_id, payload_json)
            db.execute(
                """INSERT INTO research_checkpoints
                   (task_id,revision,checkpoint_id,parent_checkpoint_id,payload_json)
                   VALUES (?,?,?,?,?)""",
                (task_id, revision, checkpoint_id, parent_id, payload_json),
            )
            row = db.execute(
                "SELECT created_at FROM research_checkpoints WHERE task_id=? AND revision=?",
                (task_id, revision),
            ).fetchone()
        return {
            "task_id": task_id, "revision": revision,
            "checkpoint_id": checkpoint_id, "parent_checkpoint_id": parent_id,
            "payload": json.loads(payload_json), "created_at": row["created_at"],
        }

    def get_latest(self, task_id: str) -> dict[str, Any] | None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        with self._connect() as db:
            row = db.execute(
                """SELECT task_id,revision,checkpoint_id,parent_checkpoint_id,
                          payload_json,created_at
                   FROM research_checkpoints WHERE task_id=?
                   ORDER BY revision DESC LIMIT 1""",
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            previous = None
            if row["revision"] > 1:
                previous = db.execute(
                    "SELECT checkpoint_id FROM research_checkpoints WHERE task_id=? AND revision=?",
                    (task_id, row["revision"] - 1),
                ).fetchone()
                if previous is None or previous["checkpoint_id"] != row["parent_checkpoint_id"]:
                    raise ValueError("checkpoint parent chain is invalid")
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("checkpoint payload is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("checkpoint payload must be an object")
        expected_id = self._checkpoint_id(
            row["task_id"], row["revision"], row["parent_checkpoint_id"],
            _canonical_json(payload),
        )
        if expected_id != row["checkpoint_id"]:
            raise ValueError("checkpoint content does not match its integrity ID")
        return {
            "task_id": row["task_id"], "revision": row["revision"],
            "checkpoint_id": row["checkpoint_id"],
            "parent_checkpoint_id": row["parent_checkpoint_id"],
            "payload": payload, "created_at": row["created_at"],
        }
