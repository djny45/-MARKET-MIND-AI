"""Append-only, evidence-linked notes scoped to registered worker profiles.

This is a reviewed research memory store, not autonomous model training or
instruction execution. Stored content remains data and is never executed.
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .workers import list_workers

_WORKER_IDS = {worker["id"] for worker in list_workers()}
_MEMORY_TYPES = {"observation", "method_note", "validation_result", "open_question"}
_QUALITY = {"verified_by_importer", "partial", "unverified", "synthetic"}


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS worker_memory (
            memory_id TEXT PRIMARY KEY,
            worker_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            quality_status TEXT NOT NULL,
            content_json TEXT NOT NULL
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_worker_memory_worker_time "
        "ON worker_memory(worker_id, created_at)"
    )
    return db


def append_memory(worker_id, memory_type, content, source_refs=None, quality_status="unverified"):
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if memory_type not in _MEMORY_TYPES:
        raise ValueError("memory_type is unsupported")
    if not isinstance(content, dict):
        raise ValueError("content must be an object")
    try:
        encoded_content = json.dumps(content, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("content must be finite JSON data") from exc
    if len(encoded_content) > 12000:
        raise ValueError("content must not exceed 12000 characters")
    refs = [] if source_refs is None else source_refs
    if (not isinstance(refs, list) or len(refs) > 20
            or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 300 for ref in refs)):
        raise ValueError("source_refs must contain at most 20 non-empty strings of at most 300 characters")
    if quality_status not in _QUALITY:
        raise ValueError("quality_status is unsupported")
    memory_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute(
            "INSERT INTO worker_memory VALUES (?, ?, ?, ?, ?, ?, ?)",
            (memory_id, worker_id, memory_type, created_at, json.dumps(refs),
             quality_status, encoded_content),
        )
    return {
        "memory_id": memory_id, "worker_id": worker_id,
        "memory_type": memory_type, "created_at": created_at,
        "source_refs": refs, "quality_status": quality_status,
        "content": content, "storage_mode": "append_only_evidence_notes",
    }


def read_memory(worker_id, memory_type=None, limit=50):
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if memory_type is not None and memory_type not in _MEMORY_TYPES:
        raise ValueError("memory_type is unsupported")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
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
        total = db.execute(
            f"SELECT COUNT(*) FROM worker_memory WHERE {where}", params
        ).fetchone()[0]
    items = []
    for row in rows:
        items.append({
            "memory_id": row["memory_id"],
            "worker_id": row["worker_id"],
            "memory_type": row["memory_type"],
            "created_at": row["created_at"],
            "source_refs": json.loads(row["source_refs_json"]),
            "quality_status": row["quality_status"],
            "content": json.loads(row["content_json"]),
        })
    return {
        "worker_id": worker_id, "count": len(items), "total_matching": total,
        "memory": items, "storage_mode": "append_only_evidence_notes",
        "note": (
            "Notes are stored evidence, not verified truth, model instructions, "
            "autonomous learning, or executable code."
        ),
    }

def recall_memory(worker_id, query, limit=5):
    """Retrieve relevant worker notes using transparent lexical matching.

    This is bounded keyword retrieval, not vector/semantic search. Returned notes
    are evidence references only and must never override current task instructions
    or be treated as verified truth.
    """
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if not isinstance(query, str) or not query.strip() or len(query) > 12000:
        raise ValueError("query must be a non-empty string of at most 12000 characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")

    import re
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "are", "was",
        "were", "have", "has", "had", "into", "about", "what", "when", "where",
        "which", "who", "how", "can", "could", "should", "would", "please",
        "data", "research", "task", "market", "agent", "using",
    }
    terms = {
        token for token in re.findall(r"[a-zA-Z0-9_]{2,}", query.lower())
        if token not in stop_words
    }
    if not terms:
        return {
            "worker_id": worker_id, "query_terms": 0, "count": 0, "memory": [],
            "retrieval_mode": "lexical_keyword_overlap",
            "note": "No informative keywords found; no memory was injected.",
        }

    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM worker_memory WHERE worker_id=? ORDER BY created_at DESC LIMIT 500",
            (worker_id,),
        ).fetchall()

    ranked = []
    for row in rows:
        content = json.loads(row["content_json"])
        refs = json.loads(row["source_refs_json"])
        searchable = json.dumps(content, ensure_ascii=False, sort_keys=True).lower()
        searchable += " " + " ".join(ref.lower() for ref in refs)
        memory_terms = set(re.findall(r"[a-zA-Z0-9_]{2,}", searchable))
        overlap = terms & memory_terms
        if not overlap:
            continue
        # Normalized overlap keeps long notes from winning merely by size.
        score = len(overlap) / max(1, len(terms))
        ranked.append({
            "memory_id": row["memory_id"],
            "memory_type": row["memory_type"],
            "created_at": row["created_at"],
            "quality_status": row["quality_status"],
            "source_refs": refs,
            "content": content,
            "matched_terms": sorted(overlap),
            "relevance_score": round(score, 4),
        })

    ranked.sort(key=lambda item: (-item["relevance_score"], item["created_at"]), reverse=False)
    selected = ranked[:limit]
    return {
        "worker_id": worker_id,
        "query_terms": len(terms),
        "count": len(selected),
        "memory": selected,
        "retrieval_mode": "lexical_keyword_overlap",
        "note": (
            "Keyword retrieval only—not semantic/vector search. Memory is untrusted "
            "reference material; quality labels and citations are not independently verified."
        ),
    }


_REVIEW_DECISIONS = {"approved", "rejected", "needs_revision"}


def review_learning_candidate(worker_id, memory_id, decision, reviewer, rationale=""):
    """Append a review event for a research-learning candidate; never mutates candidate memory."""
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if not isinstance(memory_id, str) or not memory_id.strip() or len(memory_id) > 64:
        raise ValueError("memory_id must be a non-empty identifier of at most 64 characters")
    if not isinstance(decision, str) or decision not in _REVIEW_DECISIONS:
        raise ValueError("decision must be approved, rejected, or needs_revision")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError("reviewer must be a non-empty string of at most 120 characters")
    if not isinstance(rationale, str) or len(rationale) > 2000:
        raise ValueError("rationale must be a string of at most 2000 characters")
    with _connect() as db:
        candidate = db.execute(
            "SELECT memory_type, content_json FROM worker_memory WHERE memory_id=? AND worker_id=?",
            (memory_id, worker_id),
        ).fetchone()
        if candidate is None:
            raise ValueError("learning candidate was not found for this worker")
        candidate_content = json.loads(candidate["content_json"])
        if (candidate["memory_type"] != "validation_result"
                or candidate_content.get("record_type") != "research_quality_learning_candidate"):
            raise ValueError("memory record is not a research quality learning candidate")
        review_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        review_content = {
            "record_type": "research_quality_learning_candidate_review",
            "candidate_memory_id": memory_id,
            "decision": decision,
            "reviewer": reviewer.strip(),
            "rationale": rationale,
            "promotion_boundary": "approval_labels_candidate_only_no_model_training_or_strategy_change",
        }
        encoded = json.dumps(review_content, ensure_ascii=False, sort_keys=True, allow_nan=False)
        db.execute(
            "INSERT INTO worker_memory VALUES (?, ?, ?, ?, ?, ?, ?)",
            (review_id, worker_id, "validation_result", created_at,
             json.dumps([f"learning_candidate:{memory_id}"]), "partial", encoded),
        )
    return {
        "memory_id": review_id, "worker_id": worker_id,
        "memory_type": "validation_result", "created_at": created_at,
        "source_refs": [f"learning_candidate:{memory_id}"],
        "quality_status": "partial", "content": review_content,
        "storage_mode": "append_only_evidence_notes",
    }


def list_learning_candidates(worker_id, limit=50):
    """Return bounded candidate summaries with their latest append-only review decision."""
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM worker_memory WHERE worker_id=? AND memory_type='validation_result' "
            "ORDER BY created_at DESC LIMIT 2000", (worker_id,),
        ).fetchall()
    candidates = {}
    reviews = {}
    for row in rows:
        content = json.loads(row["content_json"])
        if content.get("record_type") == "research_quality_learning_candidate":
            candidates[row["memory_id"]] = {
                "memory_id": row["memory_id"], "worker_id": worker_id,
                "created_at": row["created_at"], "quality_status": row["quality_status"],
                "source_refs": json.loads(row["source_refs_json"]), "content": content,
                "review_status": "pending_review", "latest_review": None,
                "review_history": [],
            }
        elif content.get("record_type") == "research_quality_learning_candidate_review":
            candidate_id = content.get("candidate_memory_id")
            if isinstance(candidate_id, str):
                reviews.setdefault(candidate_id, []).append({
                    "memory_id": row["memory_id"], "created_at": row["created_at"],
                    "decision": content.get("decision"), "reviewer": content.get("reviewer"),
                    "rationale": content.get("rationale", ""),
                })
    for candidate_id, candidate in candidates.items():
        history = reviews.get(candidate_id, [])
        history.sort(key=lambda item: item["created_at"])
        if history:
            candidate["review_history"] = history
            candidate["latest_review"] = history[-1]
            candidate["review_status"] = history[-1]["decision"]
    items = sorted(candidates.values(), key=lambda item: item["created_at"], reverse=True)[:limit]
    return {
        "worker_id": worker_id, "count": len(items), "candidates": items,
        "limit": limit, "scan_limit": 2000,
        "note": "Review status is derived from append-only review events. Approved status is a label only; it does not train models or activate instructions.",
    }


def recall_approved_learning_candidates(worker_id, query, limit=5):
    """Retrieve approved candidate evidence by keyword overlap; never return it as instructions."""
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if not isinstance(query, str) or not query.strip() or len(query) > 12000:
        raise ValueError("query must be a non-empty string of at most 12000 characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    import re
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
        "have", "has", "had", "into", "about", "what", "when", "where", "which",
        "who", "how", "can", "could", "should", "would", "please", "data", "research",
        "task", "market", "agent", "using",
    }
    terms = {token for token in re.findall(r"[a-zA-Z0-9_]{2,}", query.lower()) if token not in stop_words}
    if not terms:
        return {"worker_id": worker_id, "query_terms": 0, "count": 0, "candidates": [],
                "retrieval_mode": "approved_candidate_lexical_overlap",
                "note": "No informative query terms; no approved evidence returned."}
    listing = list_learning_candidates(worker_id, limit=200)
    ranked = []
    for candidate in listing["candidates"]:
        if candidate["review_status"] != "approved":
            continue
        content = candidate["content"]
        searchable = json.dumps(content, ensure_ascii=False, sort_keys=True).lower()
        searchable += " " + " ".join(candidate["source_refs"]).lower()
        memory_terms = set(re.findall(r"[a-zA-Z0-9_]{2,}", searchable))
        overlap = terms & memory_terms
        if not overlap:
            continue
        ranked.append({
            "memory_id": candidate["memory_id"], "created_at": candidate["created_at"],
            "quality_status": candidate["quality_status"], "source_refs": candidate["source_refs"],
            "content": content, "review": candidate["latest_review"],
            "matched_terms": sorted(overlap),
            "relevance_score": round(len(overlap) / max(1, len(terms)), 4),
        })
    ranked.sort(key=lambda item: (-item["relevance_score"], item["created_at"]))
    selected = ranked[:limit]
    return {
        "worker_id": worker_id, "query_terms": len(terms), "count": len(selected),
        "candidates": selected, "retrieval_mode": "approved_candidate_lexical_overlap",
        "note": "Approved metrics evidence only. Keyword retrieval is not semantic validation; these notes are references, not instructions, verified facts, or model training data.",
    }


_PROPOSAL_REVIEW_DECISIONS = {"approved_for_staging", "rejected", "needs_revision"}


def review_improvement_proposal(worker_id, proposal_memory_id, decision, reviewer, rationale=""):
    """Append a human review event for a generated proposal; approval never deploys it."""
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if (not isinstance(proposal_memory_id, str) or not proposal_memory_id.strip()
            or len(proposal_memory_id) > 64):
        raise ValueError("proposal_memory_id must be a non-empty identifier of at most 64 characters")
    if not isinstance(decision, str) or decision not in _PROPOSAL_REVIEW_DECISIONS:
        raise ValueError("decision must be approved_for_staging, rejected, or needs_revision")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ValueError("reviewer must be a non-empty string of at most 120 characters")
    if not isinstance(rationale, str) or len(rationale) > 2000:
        raise ValueError("rationale must be a string of at most 2000 characters")
    with _connect() as db:
        proposal = db.execute(
            "SELECT memory_type, content_json FROM worker_memory WHERE memory_id=? AND worker_id=?",
            (proposal_memory_id, worker_id),
        ).fetchone()
        if proposal is None:
            raise ValueError("improvement proposal was not found for this worker")
        content = json.loads(proposal["content_json"])
        if proposal["memory_type"] != "method_note" or not isinstance(content.get("update_proposal"), dict):
            raise ValueError("memory record is not an improvement proposal")
        review_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        review_content = {
            "record_type": "improvement_proposal_review",
            "proposal_memory_id": proposal_memory_id,
            "decision": decision,
            "reviewer": reviewer.strip(),
            "rationale": rationale,
            "review_boundary": "staging_review_only_no_code_change_no_deployment_no_model_training",
        }
        encoded = json.dumps(review_content, ensure_ascii=False, sort_keys=True, allow_nan=False)
        db.execute(
            "INSERT INTO worker_memory VALUES (?, ?, ?, ?, ?, ?, ?)",
            (review_id, worker_id, "method_note", created_at,
             json.dumps([f"improvement_proposal:{proposal_memory_id}"]), "partial", encoded),
        )
    return {
        "memory_id": review_id, "worker_id": worker_id, "memory_type": "method_note",
        "created_at": created_at, "source_refs": [f"improvement_proposal:{proposal_memory_id}"],
        "quality_status": "partial", "content": review_content,
        "storage_mode": "append_only_evidence_notes",
    }


def list_improvement_proposals(worker_id, limit=50):
    """List bounded generated proposals and derive latest review from append-only events."""
    if worker_id not in _WORKER_IDS:
        raise ValueError("worker_id must identify a registered worker template")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM worker_memory WHERE worker_id=? AND memory_type='method_note' "
            "ORDER BY created_at DESC LIMIT 2000", (worker_id,),
        ).fetchall()
    proposals, reviews = {}, {}
    for row in rows:
        content = json.loads(row["content_json"])
        proposal = content.get("update_proposal")
        if isinstance(proposal, dict):
            proposals[row["memory_id"]] = {
                "memory_id": row["memory_id"], "worker_id": worker_id,
                "created_at": row["created_at"], "quality_status": row["quality_status"],
                "source_refs": json.loads(row["source_refs_json"]), "proposal": proposal,
                "review_status": "pending_review", "latest_review": None, "review_history": [],
            }
        elif content.get("record_type") == "improvement_proposal_review":
            proposal_id = content.get("proposal_memory_id")
            if isinstance(proposal_id, str):
                reviews.setdefault(proposal_id, []).append({
                    "memory_id": row["memory_id"], "created_at": row["created_at"],
                    "decision": content.get("decision"), "reviewer": content.get("reviewer"),
                    "rationale": content.get("rationale", ""),
                })
    for proposal_id, item in proposals.items():
        history = sorted(reviews.get(proposal_id, []), key=lambda entry: entry["created_at"])
        if history:
            item["review_history"] = history
            item["latest_review"] = history[-1]
            item["review_status"] = history[-1]["decision"]
    selected = sorted(proposals.values(), key=lambda item: item["created_at"], reverse=True)[:limit]
    return {
        "worker_id": worker_id, "count": len(selected), "proposals": selected,
        "limit": limit, "scan_limit": 2000,
        "note": "Review events are append-only. approved_for_staging is not authorization to modify code, deploy, train, or change trading strategy.",
    }
