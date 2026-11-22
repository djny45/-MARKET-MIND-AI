"""Streaming, dry-run parser for explicit user-supplied trade event CSV mappings.

This module does not upload files, persist records, connect to venues, or touch
wallet/signing credentials. The caller owns quarantine storage and access policy.
"""
from __future__ import annotations

import csv
import hashlib
import io
import tempfile
import contextlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import BinaryIO


DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_ROWS = 1_000_000
REQUIRED_MAPPING = {"event_id", "event_time", "instrument", "event_type"}
ALLOWED_EVENT_TYPES = {
    "ORDER_CREATED", "ACKNOWLEDGED", "PARTIAL_FILL", "FILL",
    "CANCELLED", "REJECTED", "EXPIRED", "FEE",
}
ALLOWED_SIDES = {"BUY", "SELL"}


def _decimal(value: str | None, field: str, *, positive: bool = False) -> Decimal | None:
    if value is None or value.strip() == "":
        return None
    try:
        parsed = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{field} must be a valid decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("event_time must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("event_time must include a timezone")
    return parsed.astimezone(timezone.utc)


def _safe_text(value: str | None, field: str, max_length: int = 240) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length:
        raise ValueError(f"{field} must contain 1 to {max_length} characters")
    # Reject obvious credential-bearing columns rather than retaining unknown secrets.
    lowered = field.lower() + " " + cleaned.lower()
    if any(token in lowered for token in ("private_key", "secret", "seed_phrase", "api_key", "password", "token")):
        raise ValueError(f"{field} is not an accepted event field")
    return cleaned


def _spool_input(stream: BinaryIO, max_bytes: int):
    """Copy bounded chunks to a spooled temp file while hashing; never buffer the full file."""
    total = 0
    digest = hashlib.sha256()
    spool = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    try:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            if not isinstance(chunk, (bytes, bytearray)):
                raise ValueError("input stream must return bytes")
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"trade log exceeds configured {max_bytes}-byte limit")
            digest.update(chunk)
            spool.write(chunk)
        if total == 0:
            raise ValueError("trade log is empty")
        spool.seek(0)
        return spool, total, digest.hexdigest()
    except Exception:
        spool.close()
        raise


def inspect_trade_log(
    stream: BinaryIO,
    *,
    column_mapping: dict[str, str],
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_rows: int = DEFAULT_MAX_ROWS,
    sample_size: int = 5,
) -> dict:
    """Inspect a bounded CSV stream using an explicit canonical->source mapping.

    Input is copied in chunks to a spooled temporary file while hashing. Large
    inputs spill to disk; CSV rows are then decoded and processed incrementally.
    No permanent persistence or upload endpoint is provided by this module.
    """
    if not isinstance(column_mapping, dict) or not REQUIRED_MAPPING.issubset(column_mapping):
        raise ValueError("column_mapping must map event_id, event_time, instrument and event_type")
    if len(column_mapping) > 20:
        raise ValueError("column_mapping accepts at most 20 canonical fields")
    allowed_fields = REQUIRED_MAPPING | {"side", "quantity", "price", "fee", "fee_currency", "order_reference"}
    if set(column_mapping) - allowed_fields:
        raise ValueError("column_mapping contains unsupported canonical fields")
    source_names = [_safe_text(v, k, 100) for k, v in column_mapping.items()]
    if len(set(x.casefold() for x in source_names)) != len(source_names):
        raise ValueError("column_mapping source columns must be unique")
    if max_bytes < 1 or max_bytes > DEFAULT_MAX_BYTES:
        raise ValueError(f"max_bytes must be between 1 and {DEFAULT_MAX_BYTES}")
    if max_rows < 1 or max_rows > DEFAULT_MAX_ROWS:
        raise ValueError(f"max_rows must be between 1 and {DEFAULT_MAX_ROWS}")
    if sample_size < 0 or sample_size > 100:
        raise ValueError("sample_size must be between 0 and 100")

    spool, byte_count, content_hash = _spool_input(stream, max_bytes)
    text_stream = io.TextIOWrapper(spool, encoding="utf-8-sig", errors="strict", newline="")
    reader = csv.DictReader(text_stream)
    try:
        if not reader.fieldnames:
            raise ValueError("CSV header row is required")
        normalized_headers = [(name or "").strip().casefold() for name in reader.fieldnames]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("CSV contains duplicate headers after normalization")
        normalized_to_original = dict(zip(normalized_headers, reader.fieldnames))
        absent = [v for v in source_names if v.casefold() not in normalized_to_original]
        if absent:
            raise ValueError("mapped source columns missing from CSV: " + ", ".join(absent))
    
        seen_ids: set[str] = set()
        first_time = last_time = None
        instruments: dict[str, int] = {}
        accepted = rejected = duplicates = 0
        samples: list[dict] = []
    accepted_events: list[dict] = []
        rejection_reasons: dict[str, int] = {}
        for row_number, raw in enumerate(reader, start=2):
            if row_number - 1 > max_rows:
                raise ValueError(f"trade log exceeds {max_rows} data rows")
            if None in raw or any(v is None for v in raw.values()):
                rejected += 1
                rejection_reasons["column_count_mismatch"] = rejection_reasons.get("column_count_mismatch", 0) + 1
                continue
            row = {(key or "").strip().casefold(): value for key, value in raw.items()}
            try:
                event_id = _safe_text(row[column_mapping["event_id"].casefold()], "event_id")
                if event_id in seen_ids:
                    duplicates += 1
                    continue
                event_time = _timestamp(row[column_mapping["event_time"].casefold()])
                instrument = _safe_text(row[column_mapping["instrument"].casefold()], "instrument", 80).upper()
                event_type = _safe_text(row[column_mapping["event_type"].casefold()], "event_type", 40).upper()
                if event_type not in ALLOWED_EVENT_TYPES:
                    raise ValueError("unsupported event_type")
                side = None
                if "side" in column_mapping:
                    raw_side = row[column_mapping["side"].casefold()].strip().upper()
                    if raw_side:
                        if raw_side not in ALLOWED_SIDES:
                            raise ValueError("side must be BUY or SELL")
                        side = raw_side
                quantity = _decimal(row.get(column_mapping.get("quantity", "").casefold(), ""), "quantity", positive=True) if "quantity" in column_mapping else None
                price = _decimal(row.get(column_mapping.get("price", "").casefold(), ""), "price", positive=True) if "price" in column_mapping else None
                fee = _decimal(row.get(column_mapping.get("fee", "").casefold(), ""), "fee") if "fee" in column_mapping else None
                fee_currency = _safe_text(row.get(column_mapping.get("fee_currency", "").casefold(), ""), "fee_currency", 24).upper() if "fee_currency" in column_mapping and row.get(column_mapping["fee_currency"].casefold(), "").strip() else None
                order_reference = _safe_text(row.get(column_mapping.get("order_reference", "").casefold(), ""), "order_reference", 120) if "order_reference" in column_mapping and row.get(column_mapping["order_reference"].casefold(), "").strip() else None
                if fee is not None and fee < 0:
                    raise ValueError("fee must be non-negative")
                if event_type in {"PARTIAL_FILL", "FILL"} and (quantity is None or price is None or side is None):
                    raise ValueError("fill events require side, quantity and price mappings and values")
                seen_ids.add(event_id)
                first_time = event_time if first_time is None else min(first_time, event_time)
                last_time = event_time if last_time is None else max(last_time, event_time)
                instruments[instrument] = instruments.get(instrument, 0) + 1
                accepted += 1
                accepted_events.append({
                    "event_id": event_id, "event_time": event_time.isoformat(),
                    "instrument": instrument, "event_type": event_type, "side": side,
                    "quantity": str(quantity) if quantity is not None else None,
                    "price": str(price) if price is not None else None,
                    "fee": str(fee) if fee is not None else None,
                    "fee_currency": fee_currency, "order_reference": order_reference,
                    "source_row": row_number,
                })
                if len(samples) < max(0, sample_size):
                    samples.append({
                        "event_id": event_id, "event_time": event_time.isoformat(),
                        "instrument": instrument, "event_type": event_type,
                        "side": side, "quantity": str(quantity) if quantity is not None else None,
                        "price": str(price) if price is not None else None,
                        "fee": str(fee) if fee is not None else None,
                        "fee_currency": fee_currency,
                        "order_reference": order_reference,
                        "source_row": row_number,
                    })
            except (KeyError, ValueError) as exc:
                rejected += 1
                reason = str(exc)[:160]
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
    
    except UnicodeDecodeError as exc:
        raise ValueError("trade log must be valid UTF-8 CSV") from exc
    finally:
        text_stream.close()

    if accepted + rejected + duplicates == 0:
        raise ValueError("CSV contains no trade event rows")
    return {
        "status": "dry_run_only",
        "sha256": content_hash,
        "bytes": byte_count,
        "parser_version": "trade-event-csv-v2",
        "mapping": dict(column_mapping),
        "total_rows": accepted + rejected + duplicates,
        "accepted_rows": accepted,
        "rejected_rows": rejected,
        "duplicate_rows": duplicates,
        "first_event_time": first_time.isoformat() if first_time else None,
        "last_event_time": last_time.isoformat() if last_time else None,
        "instrument_counts": dict(sorted(instruments.items())),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "sample": samples,
        "accepted_events": accepted_events,
        "persistence": "not_performed",
        "broker_execution": False,
        "wallet_or_signing_access": False,
        "limitations": [
            "Dry run only; persistence requires explicit manifest review and a separate storage call.",
            "Input is spooled in bounded chunks; permanent quarantine storage and authenticated upload remain a separate service.",
            "Column semantics must be reviewed against the original archive before accepting a production mapping.",
        ],
    }
