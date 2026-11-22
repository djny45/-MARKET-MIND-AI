"""Durable, isolated storage for normalized historical trade lifecycle events.

Imports are explicit and transactional. This module does not store raw archives,
accept uploads, connect to venues, or perform wallet/signing/order execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

EVENT_TYPES = {"ORDER_CREATED", "ACKNOWLEDGED", "PARTIAL_FILL", "FILL", "CANCELLED", "REJECTED", "EXPIRED", "FEE"}
SIDES = {"BUY", "SELL"}


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""
        CREATE TABLE IF NOT EXISTS trade_event_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_sha256 TEXT NOT NULL,
            parser_version TEXT NOT NULL,
            mapping_sha256 TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('complete')),
            byte_count INTEGER NOT NULL CHECK(byte_count > 0),
            total_rows INTEGER NOT NULL CHECK(total_rows >= 0),
            accepted_rows INTEGER NOT NULL CHECK(accepted_rows >= 0),
            rejected_rows INTEGER NOT NULL CHECK(rejected_rows >= 0),
            duplicate_rows INTEGER NOT NULL CHECK(duplicate_rows >= 0),
            first_event_time TEXT,
            last_event_time TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(content_sha256, parser_version, mapping_sha256)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS normalized_trade_events (
            import_id INTEGER NOT NULL REFERENCES trade_event_imports(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL,
            event_time TEXT NOT NULL,
            instrument TEXT NOT NULL,
            event_type TEXT NOT NULL,
            side TEXT,
            quantity TEXT,
            price TEXT,
            fee TEXT,
            fee_currency TEXT,
            order_reference TEXT,
            source_row INTEGER NOT NULL,
            PRIMARY KEY(import_id, event_id),
            CHECK(side IS NULL OR side IN ('BUY','SELL')),
            CHECK(event_type IN ('ORDER_CREATED','ACKNOWLEDGED','PARTIAL_FILL','FILL','CANCELLED','REJECTED','EXPIRED','FEE'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_trade_events_instrument_time ON normalized_trade_events(instrument, event_time)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_trade_events_order_ref ON normalized_trade_events(order_reference)")
    return db


def _mapping_digest(mapping: dict) -> str:
    canonical = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal_text(value, field, *, positive=False, nonnegative=False):
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a decimal") from exc
    if not parsed.is_finite() or (positive and parsed <= 0) or (nonnegative and parsed < 0):
        raise ValueError(f"{field} is outside accepted decimal range")
    return format(parsed, "f")


def _normalize_event(row, index):
    if not isinstance(row, dict):
        raise ValueError(f"events[{index}] must be an object")
    event_id = row.get("event_id")
    instrument = row.get("instrument")
    event_type = row.get("event_type")
    event_time = row.get("event_time")
    if not isinstance(event_id, str) or not 1 <= len(event_id.strip()) <= 240:
        raise ValueError(f"events[{index}].event_id is invalid")
    if not isinstance(instrument, str) or not 1 <= len(instrument.strip()) <= 80:
        raise ValueError(f"events[{index}].instrument is invalid")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"events[{index}].event_type is unsupported")
    if not isinstance(event_time, str):
        raise ValueError(f"events[{index}].event_time is required")
    try:
        stamp = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"events[{index}].event_time is invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"events[{index}].event_time must include timezone")
    side = row.get("side")
    if side is not None and side not in SIDES:
        raise ValueError(f"events[{index}].side is invalid")
    quantity = _decimal_text(row.get("quantity"), "quantity", positive=True)
    price = _decimal_text(row.get("price"), "price", positive=True)
    fee = _decimal_text(row.get("fee"), "fee", nonnegative=True)
    if event_type in {"PARTIAL_FILL", "FILL"} and (side is None or quantity is None or price is None):
        raise ValueError(f"events[{index}] fill requires side, quantity and price")
    fee_currency = row.get("fee_currency")
    order_reference = row.get("order_reference")
    for value, field, max_length in ((fee_currency, "fee_currency", 24), (order_reference, "order_reference", 120)):
        if value is not None and (not isinstance(value, str) or len(value.strip()) > max_length):
            raise ValueError(f"events[{index}].{field} is invalid")
    source_row = row.get("source_row")
    if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 2:
        raise ValueError(f"events[{index}].source_row is invalid")
    return (
        event_id.strip(), stamp.astimezone(timezone.utc).isoformat(), instrument.strip().upper(),
        event_type, side, quantity, price, fee,
        fee_currency.strip().upper() if fee_currency else None,
        order_reference.strip() if order_reference else None, source_row,
    )


def persist_trade_event_import(manifest: dict, events: list[dict]) -> dict:
    """Atomically persist a completed dry-run result; retries are idempotent."""
    required = {"sha256", "parser_version", "mapping", "bytes", "total_rows",
                "accepted_rows", "rejected_rows", "duplicate_rows", "first_event_time", "last_event_time"}
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise ValueError("manifest is incomplete")
    if manifest.get("status") != "dry_run_only" or manifest.get("persistence") != "not_performed":
        raise ValueError("only an unpersisted dry-run manifest can be activated")
    if not isinstance(events, list) or len(events) != manifest["accepted_rows"]:
        raise ValueError("event rows must exactly match manifest accepted_rows")
    digest = manifest["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
        raise ValueError("manifest sha256 is invalid")
    if isinstance(manifest["bytes"], bool) or not isinstance(manifest["bytes"], int) or manifest["bytes"] <= 0:
        raise ValueError("manifest bytes is invalid")
    mapping_hash = _mapping_digest(manifest["mapping"])
    prepared = [_normalize_event(row, index) for index, row in enumerate(events)]
    ids = [row[0] for row in prepared]
    if len(ids) != len(set(ids)):
        raise ValueError("event_id values must be unique in one dataset")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        existing = db.execute(
            "SELECT id, accepted_rows FROM trade_event_imports WHERE content_sha256=? AND parser_version=? AND mapping_sha256=?",
            (digest.lower(), str(manifest["parser_version"]), mapping_hash),
        ).fetchone()
        if existing:
            return {"status": "already_imported", "import_id": existing["id"],
                    "accepted_rows": existing["accepted_rows"], "inserted_rows": 0}
        cursor = db.execute("""
            INSERT INTO trade_event_imports (
                content_sha256, parser_version, mapping_sha256, state, byte_count,
                total_rows, accepted_rows, rejected_rows, duplicate_rows,
                first_event_time, last_event_time, created_at
            ) VALUES (?, ?, ?, 'complete', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            digest.lower(), str(manifest["parser_version"]), mapping_hash, manifest["bytes"],
            manifest["total_rows"], manifest["accepted_rows"], manifest["rejected_rows"],
            manifest["duplicate_rows"], manifest["first_event_time"], manifest["last_event_time"], now,
        ))
        import_id = cursor.lastrowid
        db.executemany("""
            INSERT INTO normalized_trade_events (
                import_id, event_id, event_time, instrument, event_type, side,
                quantity, price, fee, fee_currency, order_reference, source_row
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(import_id, *row) for row in prepared])
    return {"status": "imported", "import_id": import_id,
            "accepted_rows": len(prepared), "inserted_rows": len(prepared)}


def list_trade_event_imports(limit=100) -> dict:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with _connect() as db:
        rows = db.execute("""
            SELECT id, parser_version, content_sha256, byte_count, state, total_rows,
                   accepted_rows, rejected_rows, duplicate_rows, first_event_time,
                   last_event_time, created_at
            FROM trade_event_imports ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    return {"count": len(rows), "imports": [dict(row) for row in rows], "limit": limit}


def query_trade_events(import_id, instrument=None, event_type=None, limit=500) -> dict:
    if isinstance(import_id, bool) or not isinstance(import_id, int) or import_id <= 0:
        raise ValueError("import_id must be a positive integer")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    clauses, params = ["import_id=?"], [import_id]
    if instrument is not None:
        clauses.append("instrument=?")
        params.append(instrument.strip().upper())
    if event_type is not None:
        if event_type not in EVENT_TYPES:
            raise ValueError("event_type is unsupported")
        clauses.append("event_type=?")
        params.append(event_type)
    with _connect() as db:
        rows = db.execute(
            "SELECT event_id,event_time,instrument,event_type,side,quantity,price,fee,fee_currency,order_reference,source_row "
            "FROM normalized_trade_events WHERE " + " AND ".join(clauses) +
            " ORDER BY event_time, source_row LIMIT ?",
            (*params, limit),
        ).fetchall()
    return {"import_id": import_id, "count": len(rows), "events": [dict(row) for row in rows], "limit": limit}
