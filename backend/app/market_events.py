"""Historical market microstructure event store.

This is an import/query layer only. It does not connect to exchanges or produce
live quotes. Each record preserves provider, venue, event/receive time, status,
units, sequence metadata and a deterministic payload digest.
"""
import hashlib
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

EVENT_TYPES = {"trade", "quote", "order_book_snapshot", "open_interest", "funding", "fx_rate"}
STATUSES = {"historical", "delayed", "end_of_day", "reference", "synthetic"}
_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS market_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            instrument_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            venue TEXT NOT NULL,
            event_time TEXT NOT NULL,
            received_at TEXT NOT NULL,
            sequence_number INTEGER,
            status TEXT NOT NULL,
            currency TEXT,
            unit TEXT,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            inserted_at TEXT NOT NULL,
            UNIQUE(provider, venue, instrument_id, event_type, event_id)
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_market_events_scope ON market_events(instrument_id, event_type, event_time)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_market_events_provider ON market_events(provider, venue, event_time)")
    return connection


def _timestamp(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc).isoformat()


def _number(value, field, minimum=None, strict_minimum=False):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    if minimum is not None and (result <= minimum if strict_minimum else result < minimum):
        op = "greater than" if strict_minimum else "at least"
        raise ValueError(f"{field} must be {op} {minimum}")
    return result


def _validate_payload(event_type, payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    p = dict(payload)
    if event_type == "trade":
        _number(p.get("price"), "payload.price", 0, True)
        _number(p.get("quantity"), "payload.quantity", 0, True)
        if p.get("side", "unknown") not in {"buy", "sell", "unknown"}:
            raise ValueError("payload.side must be buy, sell or unknown")
    elif event_type == "quote":
        bid = _number(p.get("bid_price"), "payload.bid_price", 0, True)
        ask = _number(p.get("ask_price"), "payload.ask_price", 0, True)
        if bid > ask:
            raise ValueError("quote bid_price cannot exceed ask_price")
        _number(p.get("bid_size"), "payload.bid_size", 0)
        _number(p.get("ask_size"), "payload.ask_size", 0)
    elif event_type == "order_book_snapshot":
        for side in ("bids", "asks"):
            levels = p.get(side)
            if not isinstance(levels, list) or not levels or len(levels) > 5000:
                raise ValueError(f"payload.{side} must be a non-empty array of at most 5000 levels")
            for index, level in enumerate(levels):
                if not isinstance(level, dict):
                    raise ValueError(f"payload.{side}[{index}] must be an object")
                _number(level.get("price"), f"payload.{side}[{index}].price", 0, True)
                _number(level.get("quantity"), f"payload.{side}[{index}].quantity", 0, True)
    elif event_type == "open_interest":
        _number(p.get("value"), "payload.value", 0)
        if not isinstance(p.get("unit"), str) or not p["unit"].strip():
            raise ValueError("payload.unit is required")
    elif event_type == "funding":
        _number(p.get("rate"), "payload.rate")
        if not isinstance(p.get("interval"), str) or not p["interval"].strip():
            raise ValueError("payload.interval is required")
        if not isinstance(p.get("settlement_currency"), str) or not p["settlement_currency"].strip():
            raise ValueError("payload.settlement_currency is required")
    elif event_type == "fx_rate":
        _number(p.get("rate"), "payload.rate", 0, True)
        for field in ("base", "quote", "rate_type"):
            if not isinstance(p.get(field), str) or not p[field].strip():
                raise ValueError(f"payload.{field} is required")
        if p["base"].upper() == p["quote"].upper():
            raise ValueError("FX base and quote currencies must differ")
    return p


def _clean_identifier(value, field):
    if not isinstance(value, str) or not _ID.fullmatch(value.strip()):
        raise ValueError(f"{field} must contain 1 to 128 permitted characters")
    return value.strip()


def store_market_events(events):
    if not isinstance(events, list) or not events or len(events) > 1000:
        raise ValueError("events must contain between 1 and 1000 records")
    prepared = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] must be an object")
        event_type = event.get("event_type")
        if event_type not in EVENT_TYPES:
            raise ValueError(f"events[{index}].event_type is unsupported")
        event_id = _clean_identifier(event.get("event_id"), f"events[{index}].event_id")
        instrument_id = _clean_identifier(event.get("instrument_id"), f"events[{index}].instrument_id")
        provider = _clean_identifier(event.get("provider"), f"events[{index}].provider")
        venue = _clean_identifier(event.get("venue"), f"events[{index}].venue")
        status = event.get("status", "historical")
        if status not in STATUSES:
            raise ValueError(f"events[{index}].status is unsupported")
        event_time = _timestamp(event.get("event_time"), f"events[{index}].event_time")
        received_at = _timestamp(event.get("received_at") or datetime.now(timezone.utc).isoformat(), f"events[{index}].received_at")
        sequence = event.get("sequence_number")
        if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0):
            raise ValueError(f"events[{index}].sequence_number must be a non-negative integer")
        payload = _validate_payload(event_type, event.get("payload"))
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        prepared.append((
            event_id, instrument_id, event_type, provider, venue, event_time,
            received_at, sequence, status, event.get("currency"), event.get("unit"),
            payload_json, digest, datetime.now(timezone.utc).isoformat(),
        ))
    with _connect() as connection:
        before = connection.total_changes
        connection.executemany("""
            INSERT OR IGNORE INTO market_events (
                event_id, instrument_id, event_type, provider, venue, event_time,
                received_at, sequence_number, status, currency, unit,
                payload_json, payload_sha256, inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, prepared)
        inserted = connection.total_changes - before
    return {
        "accepted": len(prepared), "inserted": inserted,
        "duplicates_ignored": len(prepared) - inserted,
        "event_types": sorted({item[2] for item in prepared}),
        "status_counts_as_submitted": {status: sum(1 for item in prepared if item[8] == status) for status in sorted({item[8] for item in prepared})},
        "data_note": "Records are historical imports or caller-supplied observations. Provider identity and status are metadata supplied by the importer, not independently authenticated.",
    }


def query_market_events(instrument_id=None, event_type=None, provider=None, venue=None, start=None, end=None, limit=500):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    if event_type is not None and event_type not in EVENT_TYPES:
        raise ValueError("event_type is unsupported")
    clauses, params = [], []
    for column, value in (("instrument_id", instrument_id), ("event_type", event_type), ("provider", provider), ("venue", venue)):
        if value is not None:
            clauses.append(f"{column}=?")
            params.append(_clean_identifier(value, column) if column != "event_type" else value)
    if start is not None:
        clauses.append("event_time>=?")
        params.append(_timestamp(start, "start"))
    if end is not None:
        clauses.append("event_time<=?")
        params.append(_timestamp(end, "end"))
    if start is not None and end is not None and _timestamp(start, "start") > _timestamp(end, "end"):
        raise ValueError("start must not be later than end")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT event_id, instrument_id, event_type, provider, venue, event_time, received_at, sequence_number, status, currency, unit, payload_json, payload_sha256 "
            "FROM market_events" + where + " ORDER BY event_time DESC, id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM market_events" + where, params).fetchone()[0]
    result = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        result.append(item)
    return {
        "count": len(result), "total_matching": total, "events": result, "limit": limit,
        "data_note": "Query returns stored historical events only; it does not establish completeness, real-time freshness or independent provider authentication.",
    }
