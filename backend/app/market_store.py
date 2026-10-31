"""SQLite storage for normalized market bars with provenance metadata."""
import os
import sqlite3
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
        }
    except (sqlite3.Error, OSError) as exc:
        return {
            "status": "not_ready",
            "reachable": False,
            "market_bars_schema": False,
            "error": type(exc).__name__,
        }
