"""Append-only, worker-scoped research memory backed by the shared SQLite store.

Entries are evidence-linked notes, not model training data or autonomous beliefs.
Only observations and methodology notes are accepted; promotion to shared
knowledge requires a separate human review workflow that is not implemented.
"""
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .workers import list_workers

MEMORY_SCHEMA_VERSION = 1
WORKER_IDS = {item["id"] for item in list_workers()}
WORKER_ID_PATTERN = re.compile(r"^worker_[0-9]{3}$")
MEMORY_TYPES = {"observation", "methodology"}
QUALITY = {"verified_by_importer", "partial", "unverified", "synthetic"}

def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS worker_memory (
            memory_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            worker_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            quality_status TEXT NOT NULL,
            review_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_worker_memory_worker_time ON worker_memory(worker_id, created_at)")
    return db

def _validate_worker(worker_id):
    if not isinstance(worker_id, str) or not WORKER_ID_PATTERN.fullmatch(worker_id):
        raise ValueError("worker_id must use the worker_NNN format")
    if worker_id not in WORKER_IDS:
        raise KeyError("worker_id was not found")

def store_worker_memory(worker_id, memory_type, content, source_refs=None, quality_status="unverified"):
    _validate_worker(worker_id)
    if memory_type not in MEMORY_TYPES:
        raise ValueError("memory_type must be observation or methodology")
    if not isinstance(content, str) or not content.strip() or len(content) > 4000:
        raise ValueError("content must contain 1 to 4000 characters")
    refs = [] if source_refs is None else source_refs
    if (not isinstance(refs, list) or len(refs) > 20
        or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 300 for ref in refs)):
        raise ValueError("source_refs must contain at most 20 non-empty strings")
    if quality_status not in QUALITY:
        raise ValueError("quality_status is unsupported")
    memory_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute(
            "INSERT INTO worker_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (memory_id, MEMORY_SCHEMA_VERSION, worker_id, memory_type, content.strip(),
             json.dumps(refs), quality_status, "pending_review", created_at),
        )
    return {
        "memory_id": memory_id, "schema_version": MEMORY_SCHEMA_VERSION,
        "worker_id": worker_id, "memory_type": memory_type,
        "content": content.strip(), "source_refs": refs,
        "quality_status": quality_status, "review_status": "pending_review",
        "created_at": created_at,
    }

def list_worker_memory(worker_id, limit=50, memory_type=None):
    _validate_worker(worker_id)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if memory_type is not None and memory_type not in MEMORY_TYPES:
        raise ValueError("memory_type must be observation or methodology")
    where = "worker_id=?"
    params = [worker_id]
    if memory_type is not None:
        where += " AND memory_type=?"
        params.append(memory_type)
    with _connect() as db:
        rows = db.execute(
            f"SELECT * FROM worker_memory WHERE {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        total = db.execute(f"SELECT COUNT(*) FROM worker_memory WHERE {where}", params).fetchone()[0]
    entries = []
    for row in rows:
        item = dict(row)
        item["source_refs"] = json.loads(item.pop("source_refs_json"))
        entries.append(item)
    return {
        "worker_id": worker_id, "count": len(entries), "total_matching": total,
        "schema_version": MEMORY_SCHEMA_VERSION, "entries": entries,
        "memory_policy": "append_only_pending_review",
        "note": "Stored notes are not model training data, verified facts, or automatically shared knowledge.",
    }
