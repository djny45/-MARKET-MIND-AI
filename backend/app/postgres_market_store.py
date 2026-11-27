"""PostgreSQL implementation of the market-store contract.

This adapter is intentionally not selected by the application yet. Callers must
apply the versioned market schema first, then explicitly wire and test this
adapter. It does not claim local-disk headroom for managed PostgreSQL.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from .postgres import database_url

DATA_NOTE = (
    "Stored observations retain per-bar source, status and retrieval timestamps; "
    "freshness is not implied. Multiple sources can contribute separate observations "
    "at one timestamp."
)


@contextmanager
def _connection(environ: dict[str, str] | None = None, *, connect: Any = None) -> Iterator[Any]:
    dsn = database_url(environ)
    if not dsn:
        raise RuntimeError("postgres_not_configured")
    if connect is None:
        import psycopg
        from psycopg.rows import dict_row
        connect = lambda value, **kwargs: psycopg.connect(value, row_factory=dict_row, **kwargs)
    with connect(dsn, connect_timeout=3) as connection:
        yield connection


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _iso(value) for key, value in dict(row).items()}


def store_batch(batch: Any, *, environ: dict[str, str] | None = None,
                connect: Any = None) -> dict:
    """Idempotently upsert one validated MarketDataBatch and append its audit event."""
    ordered = sorted(batch.bars, key=lambda bar: bar.timestamp)
    rows = [
        (
            batch.symbol.upper(), batch.interval, bar.timestamp, bar.open, bar.high,
            bar.low, bar.close, bar.volume, batch.status.value, batch.source,
            batch.retrieved_at,
        )
        for bar in batch.bars
    ]
    with _connection(environ, connect=connect) as connection:
        with connection.cursor() as cursor:
            if rows:
                cursor.executemany(
                    """
                    INSERT INTO market_bars (
                        symbol, interval, timestamp, open, high, low, close, volume,
                        status, source, retrieved_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, interval, timestamp, source) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                        close=EXCLUDED.close, volume=EXCLUDED.volume,
                        status=EXCLUDED.status, retrieved_at=EXCLUDED.retrieved_at
                    """,
                    rows,
                )
            cursor.execute(
                """
                INSERT INTO market_ingestion_audit_events (
                    event_type, symbol, interval, source, status, observation_count,
                    first_timestamp, last_timestamp, occurred_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    "market_data_batch_stored", batch.symbol.upper(), batch.interval,
                    batch.source, batch.status.value, len(rows),
                    ordered[0].timestamp if ordered else None,
                    ordered[-1].timestamp if ordered else None,
                    batch.retrieved_at,
                ),
            )
    return {
        "stored": len(rows), "symbol": batch.symbol.upper(), "interval": batch.interval,
        "source": batch.source, "status": batch.status.value,
        "first_timestamp": _iso(ordered[0].timestamp) if ordered else None,
        "last_timestamp": _iso(ordered[-1].timestamp) if ordered else None,
        "ordering": "chronological", "duplicate_timestamps": 0,
        "data_note": "Batch timestamps are unique and stored chronologically; source and retrieval metadata are retained.",
    }


def get_bars(symbol: str, interval: str, limit: int = 500, *,
             environ: dict[str, str] | None = None, connect: Any = None) -> dict:
    safe_limit = max(1, min(int(limit), 5000))
    normalized_symbol = symbol.strip().upper()
    with _connection(environ, connect=connect) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT timestamp, open, high, low, close, volume, status, source, retrieved_at
                FROM market_bars WHERE symbol=%s AND interval=%s
                ORDER BY timestamp DESC, source DESC LIMIT %s
                """,
                (normalized_symbol, interval, safe_limit),
            )
            rows = [_normalize_row(row) for row in cursor.fetchall()]
    observations = list(reversed(rows))
    sources = sorted({item["source"] for item in observations})
    statuses = sorted({item["status"] for item in observations})
    retrieved = [item["retrieved_at"] for item in observations if item.get("retrieved_at")]
    timestamps = {item["timestamp"] for item in observations}
    return {
        "symbol": normalized_symbol, "interval": interval, "count": len(observations),
        "bars": observations,
        "source": sources[0] if len(sources) == 1 else ("mixed" if sources else None),
        "sources": sources,
        "status": statuses[0] if len(statuses) == 1 else ("mixed" if statuses else None),
        "statuses": statuses, "retrieved_at": max(retrieved) if retrieved else None,
        "source_count": len(sources), "timestamp_count": len(timestamps),
        "duplicate_timestamp_observations": len(observations) - len(timestamps),
        "first_timestamp": observations[0]["timestamp"] if observations else None,
        "last_timestamp": observations[-1]["timestamp"] if observations else None,
        "data_note": DATA_NOTE,
    }


def get_audit_events(symbol: str | None = None, interval: str | None = None,
                     limit: int = 100, *, environ: dict[str, str] | None = None,
                     connect: Any = None) -> dict:
    safe_limit = max(1, min(int(limit), 500))
    clauses, params = [], []
    if symbol:
        clauses.append("symbol = %s")
        params.append(symbol.strip().upper())
    if interval:
        clauses.append("interval = %s")
        params.append(interval.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(safe_limit)
    with _connection(environ, connect=connect) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, event_type, symbol, interval, source, status, "
                "observation_count, first_timestamp, last_timestamp, occurred_at "
                "FROM market_ingestion_audit_events" + where +
                " ORDER BY id DESC LIMIT %s",
                tuple(params),
            )
            events = [_normalize_row(row) for row in cursor.fetchall()]
    return {
        "count": len(events), "events": events, "limit": safe_limit,
        "data_note": "Audit events record batch-ingestion metadata only; they do not prove provider authenticity or user identity.",
    }


def get_data_lineage(symbol: str, interval: str, limit: int = 5000, *,
                     environ: dict[str, str] | None = None, connect: Any = None) -> dict:
    safe_limit = max(1, min(int(limit), 5000))
    with _connection(environ, connect=connect) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT source, status, COUNT(*) AS observation_count,
                       MIN(timestamp) AS first_timestamp, MAX(timestamp) AS last_timestamp,
                       MAX(retrieved_at) AS latest_retrieval
                FROM (
                    SELECT source, status, timestamp, retrieved_at
                    FROM market_bars WHERE symbol=%s AND interval=%s
                    ORDER BY timestamp DESC LIMIT %s
                ) AS recent
                GROUP BY source, status ORDER BY source, status
                """,
                (symbol.strip().upper(), interval, safe_limit),
            )
            entries = [_normalize_row(row) for row in cursor.fetchall()]
    return {
        "symbol": symbol.strip().upper(), "interval": interval,
        "observation_count": sum(item["observation_count"] for item in entries),
        "lineage": entries, "limit": safe_limit,
        "data_note": "Lineage is derived from stored observation metadata; it does not authenticate providers or establish freshness.",
    }


def get_market_overview(limit: int = 200, *, environ: dict[str, str] | None = None,
                        connect: Any = None) -> dict:
    safe_limit = max(1, min(int(limit), 500))
    with _connection(environ, connect=connect) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT symbol, interval, COUNT(*) AS observation_count,
                       COUNT(DISTINCT timestamp) AS distinct_timestamp_count,
                       COUNT(DISTINCT source) AS source_count,
                       ARRAY_AGG(DISTINCT source ORDER BY source) AS sources,
                       ARRAY_AGG(DISTINCT status ORDER BY status) AS statuses,
                       MIN(timestamp) AS first_timestamp, MAX(timestamp) AS last_timestamp,
                       MAX(retrieved_at) AS latest_retrieval
                FROM market_bars GROUP BY symbol, interval
                ORDER BY symbol, interval LIMIT %s
                """,
                (safe_limit,),
            )
            coverage = []
            for raw in cursor.fetchall():
                item = _normalize_row(raw)
                item["sources"] = list(item["sources"] or [])
                item["statuses"] = list(item["statuses"] or [])
                coverage.append(item)
    return {
        "status": "stored_data_overview", "instrument_interval_count": len(coverage),
        "coverage": coverage, "limit": safe_limit,
        "data_note": "This view summarizes stored observations only. It is not a live quote, complete universe, market-wide ranking, or freshness guarantee.",
    }


def database_readiness(*, environ: dict[str, str] | None = None, connect: Any = None) -> dict:
    """Check PostgreSQL reachability, migrated schema and transaction write access."""
    try:
        with _connection(environ, connect=connect) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.execute(
                    "SELECT to_regclass('public.schema_migrations') AS migrations_table, "
                    "to_regclass('public.market_bars') AS market_bars_table"
                )
                schema_tables = cursor.fetchone() or {}
                migrations_present = bool(schema_tables.get("migrations_table"))
                present = bool(schema_tables.get("market_bars_table"))
                if not migrations_present:
                    return {
                        "status": "not_ready", "reachable": True, "writable": False,
                        "market_bars_schema": present, "schema_version": 0,
                    }
                cursor.execute("SELECT COALESCE(MAX(version), 0) AS schema_version FROM schema_migrations")
                version_row = cursor.fetchone()
                version = int(version_row["schema_version"]) if version_row else 0
                if not present or version < 1:
                    return {
                        "status": "not_ready", "reachable": True, "writable": False,
                        "market_bars_schema": present, "schema_version": version,
                    }
                # Exercise INSERT privileges using a reserved probe key, then roll
                # back so no readiness record persists in the market dataset.
                cursor.execute(
                    """
                    INSERT INTO market_bars (
                        symbol, interval, timestamp, open, high, low, close, volume,
                        status, source, retrieved_at
                    ) VALUES (
                        '__READINESS_PROBE__', '1d', TIMESTAMPTZ '2000-01-01 00:00:00+00',
                        1, 1, 1, 1, 0, 'unavailable', '__readiness_probe__',
                        CURRENT_TIMESTAMP
                    ) ON CONFLICT (symbol, interval, timestamp, source) DO NOTHING
                    """
                )
                connection.rollback()
        return {
            "status": "ready", "reachable": True, "writable": True,
            "market_bars_schema": True, "schema_version": version,
        }
    except Exception as exc:
        return {
            "status": "not_ready", "reachable": False, "writable": False,
            "market_bars_schema": False, "error": type(exc).__name__,
        }


def storage_headroom() -> dict:
    """Managed PostgreSQL does not expose host filesystem free-space metrics."""
    return {
        "status": "not_applicable",
        "note": "Database volume capacity must be monitored through the managed database provider.",
    }


__all__ = [
    "store_batch", "get_bars", "get_audit_events", "get_data_lineage",
    "get_market_overview", "database_readiness", "storage_headroom",
]
