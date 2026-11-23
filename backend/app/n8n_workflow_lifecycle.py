"""Persistent generate -> validate -> human-review lifecycle for n8n exports.

The caller supplies an agent-authored workflow export. This module validates and
stores it for review; it never imports, activates, or executes n8n workflows.
Reviewer labels are self-reported and are not authenticated identities.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from . import sqlite_tuning

from .n8n_workflow_validation import validate_n8n_workflow

MAX_WORKFLOW_CHARS = 500_000
VALID_REVIEW_DECISIONS = {"approve", "reject"}


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite_tuning.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS n8n_workflow_drafts (
        draft_id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        title TEXT NOT NULL,
        workflow_json TEXT NOT NULL,
        workflow_sha256 TEXT NOT NULL,
        validation_json TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS n8n_workflow_reviews (
        review_id TEXT PRIMARY KEY,
        draft_id TEXT NOT NULL UNIQUE,
        reviewer_label TEXT NOT NULL,
        reviewer_identity_verified INTEGER NOT NULL DEFAULT 0,
        decision TEXT NOT NULL,
        review_note TEXT NOT NULL,
        workflow_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(draft_id) REFERENCES n8n_workflow_drafts(draft_id)
    )""")
    return db


def _now():
    return datetime.now(timezone.utc).isoformat()


def submit_agent_workflow_draft(agent_id: str, title: str, workflow: dict[str, Any]) -> dict:
    """Validate and persist an agent-authored export in pending-human-review state."""
    if not isinstance(agent_id, str) or not agent_id.strip() or len(agent_id.strip()) > 120:
        raise ValueError("agent_id must contain 1 to 120 characters.")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
        raise ValueError("title must contain 1 to 120 characters.")
    try:
        workflow_json = json.dumps(workflow, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("workflow must be finite JSON-compatible data.") from exc
    if len(workflow_json) > MAX_WORKFLOW_CHARS:
        raise ValueError("workflow export exceeds the 500000-character limit.")
    validation = validate_n8n_workflow(workflow)
    if not validation["structurally_valid"]:
        raise ValueError("Workflow validation failed: " + " ".join(validation["errors"]))
    digest = hashlib.sha256(workflow_json.encode("utf-8")).hexdigest()
    draft_id = str(uuid.uuid4())
    now = _now()
    with _connect() as db:
        db.execute(
            """INSERT INTO n8n_workflow_drafts
               (draft_id,agent_id,title,workflow_json,workflow_sha256,
                validation_json,status,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (draft_id, agent_id.strip(), title.strip(), workflow_json, digest,
             json.dumps(validation, sort_keys=True), "pending_human_review", now, now),
        )
    return {
        "draft_id": draft_id, "agent_id": agent_id.strip(), "title": title.strip(),
        "status": "pending_human_review", "workflow_sha256": digest,
        "validation": validation, "created_at": now,
        "human_review_required": True, "auto_approval": False,
        "workflow_activation": False, "workflow_execution": False,
        "broker_execution": False,
    }


def get_agent_workflow_draft(draft_id: str) -> dict | None:
    with _connect() as db:
        row = db.execute(
            """SELECT d.*, r.reviewer_label, r.reviewer_identity_verified,
                      r.decision, r.review_note, r.created_at AS reviewed_at
               FROM n8n_workflow_drafts d
               LEFT JOIN n8n_workflow_reviews r ON r.draft_id=d.draft_id
               WHERE d.draft_id=?""", (draft_id,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    workflow = json.loads(item.pop("workflow_json"))
    item["validation"] = json.loads(item.pop("validation_json"))
    item["workflow"] = workflow
    if item.get("decision"):
        item["review"] = {
            "reviewer": item.pop("reviewer_label"),
            "reviewer_identity_verified": bool(item.pop("reviewer_identity_verified")),
            "decision": item.pop("decision"),
            "review_note": item.pop("review_note"),
            "reviewed_at": item.pop("reviewed_at"),
        }
    else:
        for key in ("reviewer_label", "reviewer_identity_verified", "decision", "review_note", "reviewed_at"):
            item.pop(key, None)
        item["review"] = None
    item["workflow_activation"] = False
    item["workflow_execution"] = False
    item["broker_execution"] = False
    return item


def list_agent_workflow_drafts(status: str | None = None, limit: int = 50) -> list[dict]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")
    allowed = {"pending_human_review", "approved", "rejected"}
    if status is not None and status not in allowed:
        raise ValueError("status must be pending_human_review, approved, or rejected.")
    query = "SELECT draft_id,agent_id,title,workflow_sha256,status,created_at,updated_at FROM n8n_workflow_drafts"
    params: list[Any] = []
    if status:
        query += " WHERE status=?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as db:
        rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def record_agent_workflow_review(draft_id: str, reviewer: str, decision: str, review_note: str = "", *, reviewer_identity_verified: bool = False) -> dict | None:
    """Record one immutable human-review decision; never trigger workflow activation."""
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer.strip()) > 120:
        raise ValueError("reviewer must contain 1 to 120 characters.")
    if decision not in VALID_REVIEW_DECISIONS:
        raise ValueError("decision must be approve or reject.")
    if not isinstance(review_note, str) or len(review_note) > 2000:
        raise ValueError("review_note must be at most 2000 characters.")
    now = _now()
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT workflow_sha256,status FROM n8n_workflow_drafts WHERE draft_id=?",
            (draft_id,),
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "pending_human_review":
            raise ValueError("Draft has already received a terminal review decision.")
        review_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO n8n_workflow_reviews
               (review_id,draft_id,reviewer_label,reviewer_identity_verified,
                decision,review_note,workflow_sha256,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (review_id, draft_id, reviewer.strip(), int(bool(reviewer_identity_verified)), decision, review_note.strip(),
             row["workflow_sha256"], now),
        )
        db.execute(
            "UPDATE n8n_workflow_drafts SET status=?,updated_at=? WHERE draft_id=? AND status=?",
            ("approved" if decision == "approve" else "rejected", now,
             draft_id, "pending_human_review"),
        )
    return {
        "review_id": review_id, "draft_id": draft_id,
        "status": "approved" if decision == "approve" else "rejected",
        "reviewer": reviewer.strip(), "reviewer_identity_verified": bool(reviewer_identity_verified),
        "decision": decision, "review_note": review_note.strip(),
        "workflow_sha256": row["workflow_sha256"], "reviewed_at": now,
        "workflow_activation": False, "workflow_execution": False,
        "broker_execution": False,
    }
