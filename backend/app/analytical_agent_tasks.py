"""Persistent bounded research-task lifecycle for specialist AI agents.

Tasks use each agent's distinct context and scoped memory, with one shared
intelligence provider. This is a synchronous first milestone, not a cloud
scheduler or continuously running autonomous agent.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .analytical_agent_runtime import brain_config
from .intelligence_core import synthesize_research

MAX_TASK_INPUT_CHARS = 10000
TASK_TYPE = "research_brief"

def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS analytical_agent_tasks (
        task_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, task_type TEXT NOT NULL,
        status TEXT NOT NULL, input_json TEXT NOT NULL, result_json TEXT NOT NULL,
        brain_context_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_agent_time ON analytical_agent_tasks(agent_id,created_at)")
    return db

def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Task data must be finite JSON-compatible values.") from exc

def enqueue_research_task(agent_id: str, brief: str, data: dict | list | None = None) -> dict:
    """Persist a queued task; the process-local background runner will pick it up."""
    brain = brain_config(agent_id)
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
        raise ValueError("brief must be a non-empty string of at most 4000 characters")
    if data is not None and not isinstance(data, (dict, list)):
        raise ValueError("data must be a JSON object or array")
    task_input = {"brief": brief.strip(), "data": data}
    input_json = _json(task_input)
    if len(input_json) > MAX_TASK_INPUT_CHARS:
        raise ValueError(f"Task input must not exceed {MAX_TASK_INPUT_CHARS} characters")
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("""INSERT INTO analytical_agent_tasks
          (task_id,agent_id,task_type,status,input_json,result_json,brain_context_sha256,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?)""",
          (task_id, agent_id, TASK_TYPE, "queued", input_json, "{}", brain["brain_context_sha256"], now, now))
    return {"task_id": task_id, "agent_id": agent_id, "status": "queued",
            "created_at": now, "updated_at": now, "brain_context_sha256": brain["brain_context_sha256"],
            "execution_mode": "process_local_background_task"}

def execute_queued_research_task(task_id: str) -> None:
    """Execute one persisted queued task; safe to call from FastAPI BackgroundTasks."""
    with _connect() as db:
        row = db.execute("SELECT * FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None or row["status"] != "queued":
            return
        # Claim atomically so duplicate dispatches cannot execute the same queued row.
        now = datetime.now(timezone.utc).isoformat()
        claimed = db.execute(
            "UPDATE analytical_agent_tasks SET status='running',updated_at=? WHERE task_id=? AND status='queued'",
            (now, task_id),
        )
        if claimed.rowcount != 1:
            return
        task_input = json.loads(row["input_json"])
        agent_id = row["agent_id"]
        brain = brain_config(agent_id)
    payload = {
        "agent": {"id": agent_id, "department": brain["department"], "specialty": brain["specialty"]},
        "task": task_input,
        "constraints": ["Use supplied data only.", "Distinguish facts, assumptions, and unknowns.",
                       "Do not invent missing market data.", "No trade execution or investment certainty."],
    }
    try:
        synthesis = synthesize_research(payload)
        result = {"agent_id": agent_id, "brain_context_sha256": row["brain_context_sha256"],
                  "brief": task_input["brief"], "input_data_received": task_input["data"] is not None,
                  "shared_core_result": synthesis,
                  "result_mode": "shared_core_synthesis" if synthesis.get("status") == "completed" else "provider_unavailable_or_not_configured",
                  "research_boundary": "supplied_data_only_no_live_market_fetch"}
        status = "completed"
    except Exception as exc:
        result = {"error": "Research task failed safely.", "error_type": type(exc).__name__}
        status = "failed"
    updated = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("UPDATE analytical_agent_tasks SET status=?,result_json=?,updated_at=? WHERE task_id=?",
                   (status, _json(result), updated, task_id))

def recover_interrupted_research_tasks() -> dict:
    """Requeue tasks left running by a process interruption.

    This is an explicit recovery operation; it does not itself dispatch work.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        running = db.execute(
            "SELECT task_id FROM analytical_agent_tasks WHERE status='running'"
        ).fetchall()
        db.execute(
            "UPDATE analytical_agent_tasks SET status='queued',updated_at=? WHERE status='running'",
            (now,),
        )
        queued = db.execute(
            "SELECT task_id FROM analytical_agent_tasks WHERE status='queued' ORDER BY created_at"
        ).fetchall()
    return {
        "requeued_interrupted_count": len(running),
        "queued_task_ids": [row["task_id"] for row in queued],
        "recovery_mode": "manual_requeue_no_dispatch",
        "note": "Requeued tasks require explicit dispatch; recovery does not automatically execute them.",
    }


def submit_research_task(agent_id: str, brief: str, data: dict | list | None = None) -> dict:
    brain = brain_config(agent_id)
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
        raise ValueError("brief must be a non-empty string of at most 4000 characters")
    if data is not None and not isinstance(data, (dict, list)):
        raise ValueError("data must be a JSON object or array")
    task_input = {"brief": brief.strip(), "data": data}
    input_json = _json(task_input)
    if len(input_json) > MAX_TASK_INPUT_CHARS:
        raise ValueError(f"Task input must not exceed {MAX_TASK_INPUT_CHARS} characters")
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("""INSERT INTO analytical_agent_tasks
          (task_id,agent_id,task_type,status,input_json,result_json,brain_context_sha256,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?)""",
          (task_id, agent_id, TASK_TYPE, "running", input_json, "{}", brain["brain_context_sha256"], now, now))

    # The configured core sees only supplied user data and the agent's role.
    research_payload = {
        "agent": {"id": agent_id, "department": brain["department"], "specialty": brain["specialty"]},
        "task": task_input,
        "constraints": ["Use supplied data only.", "Distinguish facts, assumptions, and unknowns.",
                       "Do not invent missing market data.", "No trade execution or investment certainty."],
    }
    try:
        synthesis = synthesize_research(research_payload)
        result = {
            "agent_id": agent_id,
            "brain_context_sha256": brain["brain_context_sha256"],
            "brief": brief.strip(),
            "input_data_received": data is not None,
            "shared_core_result": synthesis,
            "result_mode": "shared_core_synthesis" if synthesis.get("status") == "completed" else "provider_unavailable_or_not_configured",
            "research_boundary": "supplied_data_only_no_live_market_fetch",
        }
        status = "completed"
    except Exception as exc:
        result = {"error": "Research task failed safely.", "error_type": type(exc).__name__}
        status = "failed"
    result_json = _json(result)
    updated = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("UPDATE analytical_agent_tasks SET status=?,result_json=?,updated_at=? WHERE task_id=?",
                   (status, result_json, updated, task_id))
    return {"task_id": task_id, "agent_id": agent_id, "status": status,
            "created_at": now, "updated_at": updated, "result": result,
            "execution_mode": "bounded_synchronous_shared_core"}

def get_research_task(task_id: str) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        return None
    return {
        "task_id": row["task_id"], "agent_id": row["agent_id"],
        "task_type": row["task_type"], "status": row["status"],
        "input": json.loads(row["input_json"]), "result": json.loads(row["result_json"]),
        "brain_context_sha256": row["brain_context_sha256"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }

def list_research_tasks(agent_id: str, limit: int = 20) -> dict:
    brain_config(agent_id)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    with _connect() as db:
        rows = db.execute("""SELECT task_id,agent_id,task_type,status,brain_context_sha256,created_at,updated_at
          FROM analytical_agent_tasks WHERE agent_id=? ORDER BY created_at DESC LIMIT ?""",
          (agent_id, limit)).fetchall()
        total = db.execute("SELECT COUNT(*) FROM analytical_agent_tasks WHERE agent_id=?", (agent_id,)).fetchone()[0]
    return {"agent_id": agent_id, "count": len(rows), "total": total, "tasks": [dict(row) for row in rows]}


def list_recent_task_activity(limit: int = 500) -> dict:
    """Return a bounded cross-agent task activity snapshot for the network UI."""
    if not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    with _connect() as db:
        rows = db.execute(
            """SELECT task_id,agent_id,task_type,status,created_at,updated_at
               FROM analytical_agent_tasks ORDER BY updated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    tasks = [dict(row) for row in rows]
    counts = {status: sum(task["status"] == status for task in tasks)
              for status in ("queued", "running", "completed", "failed")}
    latest_by_agent = {}
    for task in tasks:
        latest_by_agent.setdefault(task["agent_id"], task)
    return {
        "task_count": len(tasks),
        "status_counts": counts,
        "latest_by_agent": latest_by_agent,
        "tasks": tasks,
        "source": "persisted_sqlite_task_records",
        "note": "This snapshot reflects recorded task lifecycle states, not continuous agent activity.",
    }
