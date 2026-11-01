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
    db.execute("""
        CREATE TABLE IF NOT EXISTS shared_knowledge (
            knowledge_id TEXT PRIMARY KEY,
            memory_id TEXT NOT NULL UNIQUE,
            worker_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            quality_status TEXT NOT NULL,
            approved_by TEXT NOT NULL,
            approval_rationale TEXT NOT NULL,
            approved_at TEXT NOT NULL
        )
    """)
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



def review_worker_memory(memory_id, decision, reviewer_id, rationale):
    """Explicitly approve or reject one pending worker note.

    reviewer_id is an asserted local reviewer label, not authenticated identity.
    """
    if not isinstance(memory_id, str) or not memory_id.strip() or len(memory_id) > 64:
        raise ValueError("memory_id is required")
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id) > 96:
        raise ValueError("reviewer_id must contain 1 to 96 characters")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 1000:
        raise ValueError("rationale must contain 1 to 1000 characters")

    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        row = db.execute(
            "SELECT * FROM worker_memory WHERE memory_id=?", (memory_id,)
        ).fetchone()
        if row is None:
            raise KeyError("memory_id was not found")
        if row["review_status"] != "pending_review":
            raise ValueError("memory entry has already been reviewed")
        refs = json.loads(row["source_refs_json"])
        if decision == "approve":
            if not refs:
                raise ValueError("shared knowledge approval requires at least one source reference")
            if row["quality_status"] == "synthetic":
                raise ValueError("synthetic fixture notes cannot be promoted to shared knowledge")
            knowledge_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO shared_knowledge VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (knowledge_id, memory_id, row["worker_id"], row["memory_type"],
                 row["content"], row["source_refs_json"], row["quality_status"],
                 reviewer_id.strip(), rationale.strip(), now),
            )
            status = "approved"
        else:
            knowledge_id = None
            status = "rejected"
        db.execute(
            "UPDATE worker_memory SET review_status=? WHERE memory_id=?",
            (status, memory_id),
        )
    return {
        "memory_id": memory_id, "knowledge_id": knowledge_id,
        "review_status": status, "reviewed_by": reviewer_id.strip(),
        "rationale": rationale.strip(), "reviewed_at": now,
        "shared_knowledge_created": decision == "approve",
        "reviewer_identity_authenticated": False,
    }


def list_shared_knowledge(limit=100):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM shared_knowledge ORDER BY approved_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    entries = []
    for row in rows:
        item = dict(row)
        item["source_refs"] = json.loads(item.pop("source_refs_json"))
        entries.append(item)
    return {
        "count": len(entries), "entries": entries,
        "policy": "explicit_human_approval_required",
        "note": "Reviewer labels are caller-supplied and not authenticated; protect these endpoints behind authentication before multi-user deployment.",
    }
