"""SQLite persistence for deterministic offline research benchmark records."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.research_benchmark_record import serialize_benchmark_record


_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_benchmark_records (
    record_id TEXT PRIMARY KEY,
    benchmark_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    record_json TEXT NOT NULL
);
"""


class BenchmarkRecordStore:
    """Small local archive; identical records are idempotent on insertion."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, benchmark_result: dict[str, Any]) -> str:
        record_json = serialize_benchmark_record(benchmark_result)
        record = json.loads(record_json)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO research_benchmark_records
                   (record_id, benchmark_id, schema_version, record_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    record["record_id"],
                    record["benchmark_id"],
                    record["record_schema_version"],
                    record_json,
                ),
            )
        return record["record_id"]

    def get(self, record_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_id, benchmark_id, schema_version, record_json FROM research_benchmark_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            record = json.loads(row["record_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("stored benchmark record is not valid JSON") from exc
        if not isinstance(record, dict):
            raise ValueError("stored benchmark record must be an object")
        if record.get("record_id") != row["record_id"]:
            raise ValueError("stored record ID does not match database index")
        if record.get("benchmark_id") != row["benchmark_id"]:
            raise ValueError("stored benchmark ID does not match database index")
        if record.get("record_schema_version") != row["schema_version"]:
            raise ValueError("stored schema version does not match database index")
        # Recompute the content-derived ID from the stored result. Checking only
        # SQLite index fields would miss edits to nested benchmark payloads.
        try:
            expected_record = json.loads(serialize_benchmark_record(record["result"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("stored benchmark record cannot be re-verified") from exc
        if expected_record != record:
            raise ValueError("stored benchmark record content does not match its record ID")
        return record

    def list_records(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer between 1 and 500")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT record_id, benchmark_id, schema_version
                   FROM research_benchmark_records
                   ORDER BY rowid DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
