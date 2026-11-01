"""SQLite storage for normalized market bars with provenance metadata."""
import os
import json
import hashlib
import sqlite3
from contextlib import closing
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
    if version > 2:
        connection.close()
        raise sqlite3.DatabaseError("database_schema_version_is_newer_than_this_application")
    if version < 1:
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )
    if version < 2:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS market_bar_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                previous_values TEXT NOT NULL,
                revised_values TEXT NOT NULL,
                previous_sha256 TEXT NOT NULL,
                revised_sha256 TEXT NOT NULL,
                previous_status TEXT NOT NULL,
                revised_status TEXT NOT NULL,
                changed_at TEXT NOT NULL
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_market_bar_revisions_scope "
            "ON market_bar_revisions(symbol, interval, source, id DESC)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (2, datetime.now(timezone.utc).isoformat()),
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
    revision_count = 0
    with _connect() as connection:
        for row in rows:
            symbol, interval, timestamp, open_, high, low, close, volume, status, source, retrieved_at = row
            existing = connection.execute("""
                SELECT open, high, low, close, volume, status
                FROM market_bars
                WHERE symbol=? AND interval=? AND timestamp=? AND source=?
            """, (symbol, interval, timestamp, source)).fetchone()
            if existing is None:
                continue
            previous_values = {
                "open": existing["open"], "high": existing["high"],
                "low": existing["low"], "close": existing["close"],
                "volume": existing["volume"],
            }
            revised_values = {
                "open": open_, "high": high, "low": low,
                "close": close, "volume": volume,
            }
            previous_payload = json.dumps(previous_values, sort_keys=True, separators=(",", ":"), allow_nan=False)
            revised_payload = json.dumps(revised_values, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if previous_payload != revised_payload or existing["status"] != status:
                connection.execute("""
                    INSERT INTO market_bar_revisions (
                        symbol, interval, timestamp, source,
                        previous_values, revised_values,
                        previous_sha256, revised_sha256,
                        previous_status, revised_status, changed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, interval, timestamp, source,
                    previous_payload, revised_payload,
                    hashlib.sha256(previous_payload.encode("utf-8")).hexdigest(),
                    hashlib.sha256(revised_payload.encode("utf-8")).hexdigest(),
                    existing["status"], status, retrieved_at,
                ))
                revision_count += 1
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
        "revision_count": revision_count,
        "data_note": "Changed existing OHLCV/status observations are recorded in an append-only revision audit before the current row is updated. Retrieval-time-only changes are not content revisions.",
    }



def get_bar_revisions(symbol: str | None = None, interval: str | None = None,
                      source: str | None = None, limit: int = 100) -> dict:
    """Return append-only revision records for previously stored observations."""
    safe_limit = max(1, min(int(limit), 500))
    clauses = []
    parameters = []
    if symbol:
        clauses.append("symbol=?")
        parameters.append(symbol.strip().upper())
    if interval:
        clauses.append("interval=?")
        parameters.append(interval.strip())
    if source:
        clauses.append("source=?")
        parameters.append(source.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, symbol, interval, timestamp, source, previous_values, "
            "revised_values, previous_sha256, revised_sha256, previous_status, "
            "revised_status, changed_at FROM market_bar_revisions" +
            where + " ORDER BY id DESC LIMIT ?",
            (*parameters, safe_limit),
        ).fetchall()
    revisions = []
    for row in rows:
        item = dict(row)
        item["previous_values"] = json.loads(item["previous_values"])
        item["revised_values"] = json.loads(item["revised_values"])
        revisions.append(item)
    return {
        "count": len(revisions),
        "revisions": revisions,
        "limit": safe_limit,
        "data_note": "Revision history records changes observed by this application after its audit table was introduced. It cannot reconstruct edits made before migration, prove vendor intent, or authenticate source data.",
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
        with closing(_connect()) as connection:
            with connection:
                connection.execute("SELECT 1").fetchone()
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_bars'"
                ).fetchone()
                schema_version = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()[0]
        return {
            "status": "ready" if table else "not_ready",
            "reachable": True,
            "market_bars_schema": bool(table),
            "schema_version": schema_version,
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


def get_market_overview(limit: int = 200) -> dict:
    """Summarize local stored-data coverage; this is not a live market overview."""
    safe_limit = max(1, min(int(limit), 500))
    with _connect() as connection:
        rows = connection.execute("""
            SELECT symbol, interval,
                   COUNT(*) AS observation_count,
                   COUNT(DISTINCT timestamp) AS distinct_timestamp_count,
                   COUNT(DISTINCT source) AS source_count,
                   GROUP_CONCAT(DISTINCT source) AS sources,
                   GROUP_CONCAT(DISTINCT status) AS statuses,
                   MIN(timestamp) AS first_timestamp,
                   MAX(timestamp) AS last_timestamp,
                   MAX(retrieved_at) AS latest_retrieval
            FROM market_bars
            GROUP BY symbol, interval
            ORDER BY symbol, interval
            LIMIT ?
        """, (safe_limit,)).fetchall()
    coverage = []
    for row in rows:
        item = dict(row)
        item["sources"] = sorted(item["sources"].split(",")) if item["sources"] else []
        item["statuses"] = sorted(item["statuses"].split(",")) if item["statuses"] else []
        coverage.append(item)
    return {
        "status": "stored_data_overview",
        "instrument_interval_count": len(coverage),
        "coverage": coverage,
        "limit": safe_limit,
        "data_note": "This view summarizes locally stored observations only. It is not a live quote, complete universe, market-wide ranking, or freshness guarantee.",
    }


def get_revised_bar_keys(symbol: str, interval: str, limit: int = 5000) -> dict:
    """Return current stored bars with at least one recorded content/status revision."""
    safe_limit = max(1, min(int(limit), 5000))
    with _connect() as connection:
        rows = connection.execute("""
            SELECT DISTINCT r.source, r.timestamp
            FROM market_bar_revisions AS r
            INNER JOIN market_bars AS b
              ON b.symbol=r.symbol AND b.interval=r.interval
             AND b.timestamp=r.timestamp AND b.source=r.source
            WHERE r.symbol=? AND r.interval=?
            ORDER BY r.timestamp DESC, r.source
            LIMIT ?
        """, (symbol.strip().upper(), interval, safe_limit)).fetchall()
    return {
        "count": len(rows),
        "keys": [{"source": row["source"], "timestamp": row["timestamp"]} for row in rows],
        "limit": safe_limit,
        "data_note": "Keys identify currently stored observations with revision history recorded by this application; pre-migration revisions cannot be reconstructed.",
    }
