"""Human-reviewed promotion of worker notes into shared research knowledge."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .worker_memory import _connect as memory_connect, _validate_worker

def _shared_connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS shared_knowledge (
        knowledge_id TEXT PRIMARY KEY, source_memory_id TEXT NOT NULL UNIQUE,
        worker_id TEXT NOT NULL, content TEXT NOT NULL, source_refs_json TEXT NOT NULL,
        quality_status TEXT NOT NULL, approved_by TEXT NOT NULL, approved_at TEXT NOT NULL,
        status TEXT NOT NULL)""")
    return db

def review_worker_memory(worker_id, memory_id, decision, reviewer, reason=""):
    _validate_worker(worker_id)
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError("reviewer must contain 1 to 120 characters")
    if not isinstance(reason, str) or len(reason) > 1000:
        raise ValueError("reason must be at most 1000 characters")
    with memory_connect() as db:
        row = db.execute("SELECT * FROM worker_memory WHERE memory_id=? AND worker_id=?",
                         (memory_id, worker_id)).fetchone()
        if row is None:
            raise KeyError("pending worker memory was not found")
        if row["review_status"] != "pending_review":
            raise ValueError("memory entry has already been reviewed")
        status = "approved" if decision == "approve" else "rejected"
        db.execute("UPDATE worker_memory SET review_status=? WHERE memory_id=?", (status, memory_id))
    if decision == "reject":
        return {"memory_id": memory_id, "review_status": "rejected", "reason": reason}
    knowledge_id = str(uuid.uuid4())
    approved_at = datetime.now(timezone.utc).isoformat()
    with _shared_connect() as db:
        db.execute("INSERT INTO shared_knowledge VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (knowledge_id, memory_id, worker_id, row["content"], row["source_refs_json"],
                    row["quality_status"], reviewer.strip(), approved_at, "approved"))
    return {"knowledge_id": knowledge_id, "memory_id": memory_id, "worker_id": worker_id,
            "review_status": "approved", "approved_by": reviewer.strip(), "approved_at": approved_at}

def list_shared_knowledge(limit=100):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with _shared_connect() as db:
        rows = db.execute("SELECT * FROM shared_knowledge WHERE status='approved' ORDER BY approved_at DESC LIMIT ?",
                          (limit,)).fetchall()
    return {"count": len(rows), "entries": [
        {**dict(row), "source_refs": json.loads(row["source_refs_json"])}
        for row in rows
    ], "policy": "human_approval_required"}
