"""Persistent provider-neutral instrument reference registry.

Reference metadata is not an exchange master and does not imply quote access.
Provider identifiers are namespaced by provider and venue to avoid ticker collisions.
"""
import os
import re
import sqlite3
from pathlib import Path

from .instruments import INSTRUMENTS

_SYMBOL = re.compile(r"^[A-Z0-9._:/-]{1,64}$")
_GROUPS = {"india", "us", "crypto", "forex"}


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS instrument_master (
            instrument_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            market TEXT NOT NULL,
            market_group TEXT NOT NULL,
            instrument_type TEXT NOT NULL,
            venue TEXT NOT NULL,
            currency TEXT NOT NULL,
            metadata_status TEXT NOT NULL DEFAULT 'reference_only',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS instrument_identifiers (
            instrument_id TEXT NOT NULL REFERENCES instrument_master(instrument_id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            venue TEXT NOT NULL,
            external_id TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            PRIMARY KEY(provider, venue, external_id),
            UNIQUE(instrument_id, provider, venue, identifier_type)
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_instrument_master_symbol ON instrument_master(symbol)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_instrument_master_group ON instrument_master(market_group, market)")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def sync_reference_catalogue():
    """Idempotently seed curated examples; never overwrite provider identifiers."""
    with _connect() as connection:
        for item in INSTRUMENTS:
            connection.execute("""
                INSERT INTO instrument_master (
                    instrument_id, symbol, name, market, market_group,
                    instrument_type, venue, currency, metadata_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reference_only')
                ON CONFLICT(instrument_id) DO UPDATE SET
                    symbol=excluded.symbol, name=excluded.name, market=excluded.market,
                    market_group=excluded.market_group, instrument_type=excluded.instrument_type,
                    venue=excluded.venue, currency=excluded.currency,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                item["instrument_id"], item["symbol"], item["name"], item["market"],
                item["market_group"], item["instrument_type"], item["venue"], item["currency"],
            ))
    return {"seeded_reference_count": len(INSTRUMENTS), "status": "reference_only"}


def search_instrument_master(query="", market_group=None, market=None, limit=50):
    if market_group is not None and market_group not in _GROUPS:
        raise ValueError("market_group must be one of india,us,crypto,forex")
    if not 1 <= int(limit) <= 200:
        raise ValueError("limit must be between 1 and 200")
    q = query.strip().casefold()
    clauses, params = [], []
    if market_group:
        clauses.append("market_group=?")
        params.append(market_group)
    if market:
        clauses.append("market=?")
        params.append(market)
    if q:
        clauses.append("(lower(symbol) LIKE ? OR lower(name) LIKE ? OR lower(venue) LIKE ? OR lower(instrument_id) LIKE ?)")
        pattern = f"%{q}%"
        params.extend([pattern] * 4)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT instrument_id, symbol, name, market, market_group, instrument_type, venue, currency, metadata_status "
            "FROM instrument_master" + where + " ORDER BY market_group, market, symbol LIMIT ?",
            (*params, int(limit)),
        ).fetchall()
        identifiers = connection.execute("""
            SELECT i.instrument_id, i.provider, i.venue, i.external_id, i.identifier_type
            FROM instrument_identifiers i
            JOIN instrument_master m ON m.instrument_id=i.instrument_id
        """).fetchall()
    mapped = {}
    for row in identifiers:
        mapped.setdefault(row["instrument_id"], []).append({
            "provider": row["provider"], "venue": row["venue"],
            "external_id": row["external_id"], "identifier_type": row["identifier_type"],
        })
    items = []
    for row in rows:
        item = dict(row)
        item["provider_identifiers"] = mapped.get(item["instrument_id"], [])
        item["quotes_included"] = False
        items.append(item)
    return {
        "count": len(items), "instruments": items,
        "data_type": "persistent_reference_metadata",
        "quotes_included": False,
        "coverage_note": "Curated reference records only; not a complete exchange master or a quote feed.",
    }


def register_provider_identifier(instrument_id, provider, venue, external_id, identifier_type="provider_symbol"):
    values = [str(x).strip() for x in (instrument_id, provider, venue, external_id, identifier_type)]
    if any(not x or len(x) > 128 for x in values):
        raise ValueError("identifier fields must contain 1 to 128 characters")
    if not _SYMBOL.fullmatch(values[3].upper()):
        raise ValueError("external_id contains unsupported characters")
    with _connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM instrument_master WHERE instrument_id=?", (values[0],)
        ).fetchone()
        if not exists:
            raise KeyError("instrument_id not found")
        try:
            connection.execute("""
                INSERT INTO instrument_identifiers
                (instrument_id, provider, venue, external_id, identifier_type)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider, venue, external_id) DO UPDATE SET
                    instrument_id=excluded.instrument_id,
                    identifier_type=excluded.identifier_type
            """, values)
        except sqlite3.IntegrityError as exc:
            raise ValueError("identifier mapping conflicts with an existing instrument mapping") from exc
    return {
        "instrument_id": values[0], "provider": values[1], "venue": values[2],
        "external_id": values[3], "identifier_type": values[4],
        "status": "registered", "quotes_included": False,
    }
