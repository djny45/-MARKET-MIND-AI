"""Single-user local watchlist persistence for research instrument references."""
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._=^:-]{0,31}$")


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            added_at TEXT NOT NULL
        )
    """)
    return connection


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not _SYMBOL.fullmatch(normalized):
        raise ValueError("symbol_format_invalid")
    return normalized


def list_symbols(limit: int = 100) -> dict:
    safe_limit = max(1, min(int(limit), 500))
    with _connect() as connection:
        rows = connection.execute(
            "SELECT symbol, added_at FROM watchlist ORDER BY added_at DESC, symbol LIMIT ?",
            (safe_limit,),
        ).fetchall()
    return {"count": len(rows), "symbols": [dict(row) for row in rows], "limit": safe_limit}


def add_symbol(symbol: str) -> dict:
    normalized = normalize_symbol(symbol)
    added_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO watchlist(symbol, added_at) VALUES (?, ?)",
            (normalized, added_at),
        )
        row = connection.execute(
            "SELECT symbol, added_at FROM watchlist WHERE symbol=?", (normalized,)
        ).fetchone()
    return {"added": True, "already_present": cursor.rowcount == 0,
            "symbol": row["symbol"], "added_at": row["added_at"]}


def remove_symbol(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM watchlist WHERE symbol=?", (normalized,))
    return cursor.rowcount > 0
