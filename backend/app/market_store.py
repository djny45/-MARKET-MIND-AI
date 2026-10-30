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
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "count": len(observations),
        "bars": observations,
        "data_note": "Stored observations retain status, source and retrieval timestamp; freshness is not implied.",
    }
