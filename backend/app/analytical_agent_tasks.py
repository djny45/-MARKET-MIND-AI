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
from .worker_memory import recall_memory
from .research_quality_eval import evaluate_research_draft

MAX_TASK_INPUT_CHARS = 10000
TASK_TYPE = "research_brief"

def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS analytical_agent_tasks (
        task_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, task_type TEXT NOT NULL,
        status TEXT NOT NULL, input_json TEXT NOT NULL, result_json TEXT NOT NULL,
        brain_context_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_agent_time ON analytical_agent_tasks(worker_id,created_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS analytical_agent_task_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
        worker_id TEXT NOT NULL, event_type TEXT NOT NULL,
        from_status TEXT, to_status TEXT, occurred_at TEXT NOT NULL,
        detail_json TEXT NOT NULL DEFAULT '{}'
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_task_events_task_time ON analytical_agent_task_events(task_id,event_id)")
    db.execute("""CREATE TABLE IF NOT EXISTS research_quality_evaluations (
        evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL UNIQUE,
        worker_id TEXT NOT NULL,
        evaluation_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES analytical_agent_tasks(task_id)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_quality_eval_worker_time ON research_quality_evaluations(worker_id,created_at)")
    return db

def _persist_quality_evaluation(task_id: str, worker_id: str, evaluation: dict) -> None:
    """Store one task-linked traceability evaluation; idempotent per task."""
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute(
            """INSERT INTO research_quality_evaluations
               (task_id,worker_id,evaluation_json,created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(task_id) DO UPDATE SET
                 worker_id=excluded.worker_id,
                 evaluation_json=excluded.evaluation_json,
                 created_at=excluded.created_at""",
            (task_id, worker_id, _json(evaluation), created_at),
        )

def get_task_quality_evaluation(task_id: str) -> dict | None:
    """Retrieve a persisted traceability evaluation linked to a known task."""
    with _connect() as db:
        task = db.execute("SELECT task_id FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if task is None:
            return None
        row = db.execute(
            "SELECT evaluation_id,task_id,worker_id,evaluation_json,created_at "
            "FROM research_quality_evaluations WHERE task_id=?", (task_id,)
        ).fetchone()
    if row is None:
        return {"task_id": task_id, "evaluation": None, "status": "not_evaluated"}
    return {
        "evaluation_id": row["evaluation_id"], "task_id": row["task_id"],
        "worker_id": row["worker_id"], "evaluation": json.loads(row["evaluation_json"]),
        "created_at": row["created_at"], "status": "persisted",
    }

def _record_event(db, task_id, worker_id, event_type, from_status=None, to_status=None, detail=None, occurred_at=None):
    db.execute(
        """INSERT INTO analytical_agent_task_events
           (task_id,worker_id,event_type,from_status,to_status,occurred_at,detail_json)
           VALUES (?,?,?,?,?,?,?)""",
        (task_id, worker_id, event_type, from_status, to_status,
         occurred_at or datetime.now(timezone.utc).isoformat(), _json(detail or {})),
    )

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
          (task_id,worker_id,task_type,status,input_json,result_json,brain_context_sha256,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?)""",
          (task_id, agent_id, TASK_TYPE, "queued", input_json, "{}", brain["brain_context_sha256"], now, now))
        _record_event(db, task_id, agent_id, "task_queued", to_status="queued", occurred_at=now)
    return {"task_id": task_id, "agent_id": agent_id, "worker_id": agent_id, "status": "queued",
            "created_at": now, "updated_at": now, "brain_context_sha256": brain["brain_context_sha256"],
            "execution_mode": "process_local_background_task"}

def execute_queued_research_task(task_id: str) -> None:
    """Execute one persisted queued task; safe to call from FastAPI BackgroundTasks."""
    with _connect() as db:
        row = db.execute("SELECT * FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None or row["status"] != "queued":
            return False
        # Claim atomically so duplicate dispatches cannot execute the same queued row.
        now = datetime.now(timezone.utc).isoformat()
        claimed = db.execute(
            "UPDATE analytical_agent_tasks SET status='running',updated_at=? WHERE task_id=? AND status='queued'",
            (now, task_id),
        )
        if claimed.rowcount != 1:
            return False
        _record_event(db, task_id, row["worker_id"], "task_claimed",
                      from_status="queued", to_status="running", occurred_at=now)
        agent_id = row["worker_id"]
    try:
        # Decode persisted input and load the worker context inside the guarded
        # execution block. A corrupt row or runtime-context failure must not
        # leave a task permanently marked as running.
        task_input = json.loads(row["input_json"])
        brain = brain_config(agent_id)
        # Memory retrieval and payload construction are part of execution too:
        # failures here must not strand a claimed task in "running".
        payload = {
            "agent": {"id": agent_id, "department": brain["department"], "specialty": brain["specialty"]},
            "agent_context": brain["brain_context"],
            "retrieved_memory": recall_memory(
                agent_id, task_input["brief"] + " " + json.dumps(task_input.get("data"), ensure_ascii=False)[:6000],
                limit=5,
            ),
            "task": task_input,
            "constraints": ["Use supplied data only.", "Distinguish facts, assumptions, and unknowns.",
                           "Do not invent missing market data.", "No trade execution or investment certainty."],
        }
        synthesis = synthesize_research(payload)
        task_data = task_input.get("data")
        evaluation = None
        evaluation_status = "not_requested_or_missing_structured_claims"
        if isinstance(task_data, dict) and isinstance(task_data.get("claims"), list) and isinstance(task_data.get("source_registry"), list):
            candidate_draft = synthesis.get("summary") if synthesis.get("status") == "completed" else task_data.get("draft")
            if isinstance(candidate_draft, str) and candidate_draft.strip():
                try:
                    evaluation = evaluate_research_draft(
                        draft=candidate_draft,
                        claims=task_data["claims"],
                        source_registry=task_data["source_registry"],
                        baseline=task_data.get("baseline"),
                    )
                    evaluation_status = "evaluated"
                except ValueError as exc:
                    # Optional quality metadata must not turn a successful research
                    # synthesis into a failed task. Preserve the bounded error detail.
                    evaluation_status = "invalid_evaluation_input"
                    evaluation = {
                        "status": "invalid_input",
                        "error": str(exc)[:500],
                        "evaluation_type": "deterministic_research_traceability_check",
                    }
            else:
                evaluation_status = "structured_claims_present_but_no_draft"
        if evaluation is not None:
            _persist_quality_evaluation(task_id, agent_id, evaluation)
        result = {"agent_id": agent_id, "brain_context_sha256": row["brain_context_sha256"],
                  "brief": task_input["brief"], "input_data_received": task_input["data"] is not None,
                  "shared_core_result": synthesis,
                  "research_quality_evaluation": evaluation,
                  "research_quality_evaluation_status": evaluation_status,
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
        _record_event(db, task_id, agent_id, "task_" + status,
                      from_status="running", to_status=status, occurred_at=updated,
                      detail={"error_type": result.get("error_type")} if status == "failed" else {})
    return True


def recover_interrupted_research_tasks(stale_after_seconds: int = 900) -> dict:
    """Requeue only stale running tasks; this explicit operation never dispatches.

    A grace period reduces the chance of requeueing work that is still active.
    """
    if (isinstance(stale_after_seconds, bool) or not isinstance(stale_after_seconds, int)
            or stale_after_seconds < 1):
        raise ValueError("stale_after_seconds must be a positive integer")
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    cutoff = datetime.fromtimestamp(
        now_dt.timestamp() - stale_after_seconds, timezone.utc
    ).isoformat()
    with _connect() as db:
        stale = db.execute(
            "SELECT task_id FROM analytical_agent_tasks WHERE status='running' AND updated_at < ?",
            (cutoff,),
        ).fetchall()
        db.execute(
            "UPDATE analytical_agent_tasks SET status='queued',updated_at=? "
            "WHERE status='running' AND updated_at < ?",
            (now, cutoff),
        )
        for task in stale:
            task_row = db.execute(
                "SELECT worker_id FROM analytical_agent_tasks WHERE task_id=?", (task["task_id"],)
            ).fetchone()
            _record_event(db, task["task_id"], task_row["worker_id"], "task_requeued",
                          from_status="running", to_status="queued", occurred_at=now,
                          detail={"reason": "stale_recovery", "stale_after_seconds": stale_after_seconds})
        still_running = db.execute(
            "SELECT COUNT(*) FROM analytical_agent_tasks WHERE status='running'"
        ).fetchone()[0]
        queued = db.execute(
            "SELECT task_id FROM analytical_agent_tasks WHERE status='queued' ORDER BY created_at"
        ).fetchall()
    return {
        "requeued_interrupted_count": len(stale),
        "queued_task_ids": [row["task_id"] for row in queued],
        "still_running_count": still_running,
        "stale_after_seconds": stale_after_seconds,
        "recovery_mode": "manual_stale_requeue_no_dispatch",
        "note": "Only tasks older than the recovery grace period are requeued; dispatch remains explicit.",
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
          (task_id,worker_id,task_type,status,input_json,result_json,brain_context_sha256,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?)""",
          (task_id, agent_id, TASK_TYPE, "running", input_json, "{}", brain["brain_context_sha256"], now, now))
        _record_event(db, task_id, agent_id, "task_submitted",
                      from_status=None, to_status="running", occurred_at=now,
                      detail={"execution_mode": "bounded_synchronous_shared_core"})

    try:
        # The configured core sees only supplied user data and the agent's role.
        # Memory retrieval belongs inside the guarded block after task creation.
        research_payload = {
            "agent": {"id": agent_id, "department": brain["department"], "specialty": brain["specialty"]},
            "agent_context": brain["brain_context"],
            "retrieved_memory": recall_memory(
                agent_id, brief.strip() + " " + json.dumps(data, ensure_ascii=False)[:6000],
                limit=5,
            ),
            "task": task_input,
            "constraints": ["Use supplied data only.", "Distinguish facts, assumptions, and unknowns.",
                           "Do not invent missing market data.", "No trade execution or investment certainty."],
        }
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
        _record_event(db, task_id, agent_id, "task_" + status,
                      from_status="running", to_status=status, occurred_at=updated,
                      detail={"execution_mode": "bounded_synchronous_shared_core",
                              "error_type": result.get("error_type")} if status == "failed"
                      else {"execution_mode": "bounded_synchronous_shared_core"})
    return {"task_id": task_id, "agent_id": agent_id, "worker_id": agent_id, "status": status,
            "created_at": now, "updated_at": updated, "result": result,
            "execution_mode": "bounded_synchronous_shared_core"}

def list_task_audit_events(
    task_id: str, limit: int = 100, event_type: str | None = None,
    before_event_id: int | None = None,
) -> dict:
    """Return chronological audit events before an event ID, optionally filtered by type."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if event_type is not None and (
        not isinstance(event_type, str) or not event_type.strip() or len(event_type) > 80
    ):
        raise ValueError("event_type must contain 1 to 80 characters")
    if before_event_id is not None and (
        not isinstance(before_event_id, int) or isinstance(before_event_id, bool)
        or before_event_id < 1
    ):
        raise ValueError("before_event_id must be a positive integer")
    with _connect() as db:
        exists = db.execute("SELECT task_id FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if exists is None:
            return {"task_id": task_id, "count": 0, "events": [], "next_before_event_id": None}
        clauses = ["task_id=?"]
        params: list[Any] = [task_id]
        if event_type is not None:
            clauses.append("event_type=?")
            params.append(event_type.strip())
        if before_event_id is not None:
            clauses.append("event_id<?")
            params.append(before_event_id)
        where = " AND ".join(clauses)
        rows = db.execute(
            f"""SELECT event_id,task_id,worker_id,event_type,from_status,to_status,occurred_at,detail_json
                FROM analytical_agent_task_events WHERE {where}
                ORDER BY event_id DESC LIMIT ?""",
            (*params, limit),
        ).fetchall()
    events = []
    for row in reversed(rows):
        event = dict(row)
        event["detail"] = json.loads(event.pop("detail_json"))
        events.append(event)
    next_cursor = rows[-1]["event_id"] if len(rows) == limit else None
    return {
        "task_id": task_id, "count": len(events), "events": events,
        "next_before_event_id": next_cursor,
    }

def get_research_task(task_id: str) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        return None
    input_decode_error = False
    try:
        task_input = json.loads(row["input_json"])
    except (json.JSONDecodeError, TypeError):
        # Keep task status/result inspectable even when persisted input is corrupt.
        task_input = None
        input_decode_error = True
    return {
        "task_id": row["task_id"], "agent_id": row["worker_id"], "worker_id": row["worker_id"],
        "task_type": row["task_type"], "status": row["status"],
        "input": task_input, "input_decode_error": input_decode_error,
        "result": json.loads(row["result_json"]),
        "brain_context_sha256": row["brain_context_sha256"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }

def list_research_tasks(agent_id: str, limit: int = 20) -> dict:
    brain_config(agent_id)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    with _connect() as db:
        rows = db.execute("""SELECT task_id,worker_id,task_type,status,brain_context_sha256,created_at,updated_at
          FROM analytical_agent_tasks WHERE worker_id=? ORDER BY created_at DESC LIMIT ?""",
          (agent_id, limit)).fetchall()
        total = db.execute("SELECT COUNT(*) FROM analytical_agent_tasks WHERE worker_id=?", (agent_id,)).fetchone()[0]
    return {"agent_id": agent_id, "worker_id": agent_id, "count": len(rows), "total": total, "tasks": [{**dict(row), "agent_id": row["worker_id"]} for row in rows]}


def list_recent_task_activity(limit: int = 500) -> dict:
    """Return a bounded cross-agent task activity snapshot for the network UI."""
    if not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    with _connect() as db:
        rows = db.execute(
            """SELECT task_id,worker_id,task_type,status,created_at,updated_at
               FROM analytical_agent_tasks ORDER BY updated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        event_rows = db.execute(
            """SELECT event_id,task_id,worker_id,event_type,from_status,to_status,occurred_at,detail_json
               FROM analytical_agent_task_events ORDER BY event_id DESC LIMIT ?""",
            (min(limit, 1000),),
        ).fetchall()
    tasks = [{**dict(row), "agent_id": row["worker_id"]} for row in rows]
    recent_events = []
    for row in reversed(event_rows):
        event = dict(row)
        event["detail"] = json.loads(event.pop("detail_json"))
        recent_events.append(event)
    counts = {status: sum(task["status"] == status for task in tasks)
              for status in ("queued", "running", "completed", "failed")}
    latest_by_agent = {}
    for task in tasks:
        latest_by_agent.setdefault(task["worker_id"], task)
    return {
        "task_count": len(tasks),
        "status_counts": counts,
        "latest_by_agent": latest_by_agent,
        "tasks": tasks,
        "recent_audit_events": recent_events,
        "audit_event_count": len(recent_events),
        "source": "persisted_sqlite_task_records_and_audit_events",
        "note": "This snapshot reflects recorded task lifecycle states and bounded audit events, not continuous agent activity.",
    }


def agent_supervisor_status() -> dict:
    """Return a point-in-time health snapshot of persisted agent task states."""
    with _connect() as db:
        rows = db.execute(
            "SELECT status, COUNT(*) AS count FROM analytical_agent_tasks GROUP BY status"
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM analytical_agent_tasks").fetchone()[0]
    counts = {state: 0 for state in ("queued", "running", "completed", "failed")}
    counts.update({row["status"]: row["count"] for row in rows})
    return {
        "supervisor": "manual_dispatch_supervisor",
        "status": "healthy",
        "task_count": total,
        "status_counts": counts,
        "registered_agent_count": 550,
        "dispatch_mode": "explicit_bounded_dispatch",
        "continuous_daemon": False,
        "distributed_queue": False,
    }


def dispatch_queued_research_tasks(limit: int = 50, max_concurrency: int = 4) -> dict:
    """Dispatch a bounded snapshot of queued tasks concurrently on this process."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 550:
        raise ValueError("limit must be an integer between 1 and 550")
    if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or not 1 <= max_concurrency <= 16:
        raise ValueError("max_concurrency must be an integer between 1 and 16")
    with _connect() as db:
        rows = db.execute(
            "SELECT task_id FROM analytical_agent_tasks WHERE status='queued' ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()
    task_ids = [row["task_id"] for row in rows]
    if not task_ids:
        return {"selected": 0, "dispatched": 0, "task_status_counts": {},
                "failed_task_count": 0, "max_concurrency": max_concurrency,
                "status": "idle", "task_ids": []}
    dispatch_id = str(uuid.uuid4())
    selected_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        for task_id in task_ids:
            task = db.execute(
                "SELECT worker_id FROM analytical_agent_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if task is not None:
                _record_event(db, task_id, task["worker_id"], "task_dispatch_selected",
                              from_status="queued", to_status="queued", occurred_at=selected_at,
                              detail={"dispatch_id": dispatch_id, "max_concurrency": max_concurrency})
    completed = []
    with ThreadPoolExecutor(max_workers=min(max_concurrency, len(task_ids)),
                            thread_name_prefix="market-mind-supervisor") as pool:
        futures = {pool.submit(execute_queued_research_task, task_id): task_id for task_id in task_ids}
        for future in as_completed(futures):
            task_id = futures[future]
            try:
                claimed = future.result()
                if claimed:
                    completed.append(task_id)
            except Exception:
                # One task failure must not interrupt dispatch of sibling tasks.
                continue
    finished_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        for task_id in completed:
            task = db.execute(
                "SELECT worker_id,status FROM analytical_agent_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if task is not None:
                _record_event(db, task_id, task["worker_id"], "task_dispatch_finished",
                              from_status=task["status"], to_status=task["status"],
                              occurred_at=finished_at,
                              detail={"dispatch_id": dispatch_id})
    with _connect() as db:
        placeholders = ",".join("?" for _ in task_ids)
        status_rows = db.execute(
            f"SELECT status, COUNT(*) AS count FROM analytical_agent_tasks "
            f"WHERE task_id IN ({placeholders}) GROUP BY status",
            task_ids,
        ).fetchall()
    task_status_counts = {row["status"]: row["count"] for row in status_rows}
    failed_task_count = task_status_counts.get("failed", 0)
    return {
        "selected": len(task_ids),
        "dispatched": len(completed),
        "task_status_counts": task_status_counts,
        "failed_task_count": failed_task_count,
        "max_concurrency": min(max_concurrency, len(task_ids)),
        "status": "completed",
        "task_ids": task_ids,
        "dispatch_mode": "bounded_process_local_queue_snapshot",
        "note": "Dispatch finished; task_status_counts reports each task's persisted outcome. Tasks are persisted in SQLite, but dispatch is explicit and process-local, not a continuously running distributed supervisor.",
    }
