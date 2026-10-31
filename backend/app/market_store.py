"""SQLite storage for normalized market bars with provenance metadata."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .market_data import MarketDataBatch


def _database_path() -> Path:
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect():
    connection = sqlite3.connect(_database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS market_bars (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            PRIMARY KEY (symbol, interval, timestamp, source)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            observation_count INTEGER NOT NULL,
            first_timestamp TEXT,
            last_timestamp TEXT,
            occurred_at TEXT NOT NULL
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_scope "
        "ON audit_events(symbol, interval, id DESC)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    version = connection.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
    ).fetchone()[0]
    if version > 1:
        connection.close()
        raise sqlite3.DatabaseError("database_schema_version_is_newer_than_this_application")
    if version < 1:
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_market_bars_lookup "
        "ON market_bars(symbol, interval, timestamp)"
    )
    return connection


def store_batch(batch: MarketDataBatch) -> dict:
    """Idempotently upsert a batch; retain source and freshness per observation."""
    ordered_bars = sorted(batch.bars, key=lambda bar: bar.timestamp)
    rows = [
        (
            batch.symbol.upper(), batch.interval, bar.timestamp.isoformat(),
            bar.open, bar.high, bar.low, bar.close, bar.volume,
            batch.status.value, batch.source, batch.retrieved_at.isoformat(),
        )
        for bar in batch.bars
    ]
    with _connect() as connection:
        connection.executemany("""
            INSERT INTO market_bars (
                symbol, interval, timestamp, open, high, low, close, volume,
                status, source, retrieved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, interval, timestamp, source) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                status=excluded.status, retrieved_at=excluded.retrieved_at
        """, rows)
        connection.execute("""
            INSERT INTO audit_events (
                event_type, symbol, interval, source, status, observation_count,
                first_timestamp, last_timestamp, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "market_data_batch_stored", batch.symbol.upper(), batch.interval,
            batch.source, batch.status.value, len(rows),
            ordered_bars[0].timestamp.isoformat() if ordered_bars else None,
            ordered_bars[-1].timestamp.isoformat() if ordered_bars else None,
            batch.retrieved_at.isoformat(),
        ))
    return {
        "stored": len(rows),
        "symbol": batch.symbol.upper(),
        "interval": batch.interval,
        "source": batch.source,
        "status": batch.status.value,
        "first_timestamp": ordered_bars[0].timestamp.isoformat() if ordered_bars else None,
        "last_timestamp": ordered_bars[-1].timestamp.isoformat() if ordered_bars else None,
        "ordering": "chronological",
        "duplicate_timestamps": 0,
        "data_note": "Batch timestamps are unique and stored chronologically; source and retrieval metadata are retained.",
    }


def get_bars(symbol: str, interval: str, limit: int = 500) -> dict:
    safe_limit = max(1, min(int(limit), 5000))
    with _connect() as connection:
        rows = connection.execute("""
            SELECT timestamp, open, high, low, close, volume,
                   status, source, retrieved_at
            FROM market_bars
            WHERE symbol=? AND interval=?
            ORDER BY timestamp DESC LIMIT ?
        """, (symbol.strip().upper(), interval, safe_limit)).fetchall()
    observations = [dict(row) for row in reversed(rows)]
    sources = sorted({item["source"] for item in observations})
    statuses = sorted({item["status"] for item in observations})
    retrieved_values = [item["retrieved_at"] for item in observations if item.get("retrieved_at")]
    unique_timestamps = {item["timestamp"] for item in observations}
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "count": len(observations),
        "bars": observations,
        "source": sources[0] if len(sources) == 1 else ("mixed" if sources else None),
        "sources": sources,
        "status": statuses[0] if len(statuses) == 1 else ("mixed" if statuses else None),
        "statuses": statuses,
        "retrieved_at": max(retrieved_values) if retrieved_values else None,
        "source_count": len(sources),
        "timestamp_count": len(unique_timestamps),
        "duplicate_timestamp_observations": len(observations) - len(unique_timestamps),
        "first_timestamp": observations[0]["timestamp"] if observations else None,
        "last_timestamp": observations[-1]["timestamp"] if observations else None,
        "data_note": "Stored observations retain per-bar source, status and retrieval timestamps; freshness is not implied. Multiple sources can contribute separate observations at one timestamp.",
    }



def database_readiness() -> dict:
    """Check SQLite connectivity and schema availability without exposing its path."""
    try:
        with _connect() as connection:
            connection.execute("SELECT 1").fetchone()
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_bars'"
            ).fetchone()
        return {
            "status": "ready" if table else "not_ready",
            "reachable": True,
            "market_bars_schema": bool(table),
            "schema_version": connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0],
        }
    except (sqlite3.Error, OSError) as exc:
        return {
            "status": "not_ready",
            "reachable": False,
            "market_bars_schema": False,
            "error": type(exc).__name__,
        }


def get_audit_events(symbol: str | None = None, interval: str | None = None,
                     limit: int = 100) -> dict:
    """Return recent batch-ingestion audit events; never includes raw price data."""
    safe_limit = max(1, min(int(limit), 500))
    clauses = []
    parameters = []
    if symbol:
        clauses.append("symbol=?")
        parameters.append(symbol.strip().upper())
    if interval:
        clauses.append("interval=?")
        parameters.append(interval.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, event_type, symbol, interval, source, status, "
            "observation_count, first_timestamp, last_timestamp, occurred_at "
            "FROM audit_events" + where + " ORDER BY id DESC LIMIT ?",
            (*parameters, safe_limit),
        ).fetchall()
    return {
        "count": len(rows),
        "events": [dict(row) for row in rows],
        "limit": safe_limit,
        "data_note": "Audit events record batch-ingestion metadata only; they do not prove provider authenticity or user identity.",
    }


def get_data_lineage(symbol: str, interval: str, limit: int = 5000) -> dict:
    """Summarize stored observations by source and status for a symbol/interval."""
    safe_limit = max(1, min(int(limit), 5000))
    with _connect() as connection:
        rows = connection.execute("""
            SELECT source, status, COUNT(*) AS observation_count,
                   MIN(timestamp) AS first_timestamp,
                   MAX(timestamp) AS last_timestamp,
                   MAX(retrieved_at) AS latest_retrieval
            FROM (
                SELECT source, status, timestamp, retrieved_at
                FROM market_bars
                WHERE symbol=? AND interval=?
                ORDER BY timestamp DESC
                LIMIT ?
            )
            GROUP BY source, status
            ORDER BY source, status
        """, (symbol.strip().upper(), interval, safe_limit)).fetchall()
    entries = [dict(row) for row in rows]
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "observation_count": sum(item["observation_count"] for item in entries),
        "lineage": entries,
        "limit": safe_limit,
        "data_note": "Lineage is derived from stored observation metadata; it does not authenticate providers or establish freshness.",
    }
