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
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .analytical_agent_runtime import brain_config, set_agent_scope, reset_agent_scope
from .intelligence_core import synthesize_research
from .worker_memory import recall_memory
from .research_quality_eval import evaluate_research_draft

MAX_TASK_INPUT_CHARS = 10000
MAX_TASK_EXECUTION_ATTEMPTS = 3
TASK_TYPE = "research_brief"

@contextmanager
def _connect():
    """Open a task-store connection for one operation and always close it.

    Commit successful operations and roll back failures before releasing the
    connection. This avoids leaking SQLite handles from frequent task polling.
    """
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS analytical_agent_tasks (
            task_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, task_type TEXT NOT NULL,
            status TEXT NOT NULL, input_json TEXT NOT NULL, result_json TEXT NOT NULL,
            brain_context_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_agent_time ON analytical_agent_tasks(worker_id,created_at)")
        # Backward-compatible schema migration for persisted task execution telemetry.
        task_columns = {row["name"] for row in db.execute("PRAGMA table_info(analytical_agent_tasks)")}
        if "execution_attempts" not in task_columns:
            db.execute("ALTER TABLE analytical_agent_tasks ADD COLUMN execution_attempts INTEGER NOT NULL DEFAULT 0")
        if "execution_token" not in task_columns:
            db.execute("ALTER TABLE analytical_agent_tasks ADD COLUMN execution_token TEXT")
        db.execute("""CREATE TABLE IF NOT EXISTS analytical_agent_task_retries (
            original_task_id TEXT PRIMARY KEY,
            retry_task_id TEXT NOT NULL UNIQUE,
            requested_at TEXT NOT NULL
        )""")
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
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

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

def cancel_queued_research_task(task_id: str) -> dict | None:
    """Cancel only queued tasks; running and terminal tasks are not interrupted."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        row = db.execute(
            "SELECT worker_id,status FROM analytical_agent_tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "queued":
            return {"task_id": task_id, "worker_id": row["worker_id"],
                    "status": row["status"], "cancelled": False,
                    "reason": "task_not_queued"}
        changed = db.execute(
            """UPDATE analytical_agent_tasks SET status='cancelled',
               result_json=?,updated_at=? WHERE task_id=? AND status='queued'""",
            (_json({"status": "cancelled", "reason": "cancelled_before_execution"}), now, task_id),
        )
        if changed.rowcount != 1:
            latest = db.execute(
                "SELECT worker_id,status FROM analytical_agent_tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
            return {"task_id": task_id, "worker_id": latest["worker_id"],
                    "status": latest["status"], "cancelled": False,
                    "reason": "task_state_changed"}
        _record_event(db, task_id, row["worker_id"], "task_cancelled",
                      from_status="queued", to_status="cancelled", occurred_at=now,
                      detail={"reason": "cancelled_before_execution"})
    return {"task_id": task_id, "worker_id": row["worker_id"],
            "status": "cancelled", "cancelled": True}

def retry_failed_research_task(task_id: str) -> dict | None:
    """Create one fresh queued retry for a failed task; never rerun in place."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")
    now = datetime.now(timezone.utc).isoformat()
    retry_task_id = str(uuid.uuid4())
    with _connect() as db:
        # Serialize retry requests so concurrent API calls cannot create multiple
        # retry tasks for the same original failure.
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT worker_id,task_type,status,input_json,brain_context_sha256 "
            "FROM analytical_agent_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "failed":
            return {"task_id": task_id, "status": row["status"], "retried": False,
                    "reason": "task_not_failed"}
        # Do not allow retry-of-retry chains: one retry maximum per task lineage.
        queued_event_rows = db.execute(
            "SELECT detail_json FROM analytical_agent_task_events "
            "WHERE task_id=? AND event_type='task_queued'", (task_id,)
        ).fetchall()
        is_retry_task = any(
            isinstance((detail := json.loads(event["detail_json"])), dict)
            and detail.get("retry_of_task_id")
            for event in queued_event_rows
        )
        if is_retry_task:
            return {"task_id": task_id, "status": "failed", "retried": False,
                    "reason": "retry_limit_reached", "retry_limit": 1,
                    "retry_task_id": None, "retry_lineage_limit": 1}
        existing = db.execute(
            "SELECT retry_task_id FROM analytical_agent_task_retries WHERE original_task_id=?",
            (task_id,),
        ).fetchone()
        if existing is not None:
            return {"task_id": task_id, "status": "failed", "retried": False,
                    "reason": "retry_limit_reached", "retry_limit": 1,
                    "retry_task_id": existing["retry_task_id"]}
        db.execute(
            """INSERT INTO analytical_agent_tasks
               (task_id,worker_id,task_type,status,input_json,result_json,
                brain_context_sha256,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (retry_task_id, row["worker_id"], row["task_type"], "queued",
             row["input_json"], "{}", row["brain_context_sha256"], now, now),
        )
        db.execute(
            "INSERT INTO analytical_agent_task_retries (original_task_id,retry_task_id,requested_at) "
            "VALUES (?,?,?)", (task_id, retry_task_id, now)
        )
        _record_event(db, task_id, row["worker_id"], "task_retry_requested",
                      from_status="failed", to_status="failed", occurred_at=now,
                      detail={"retry_task_id": retry_task_id, "retry_limit": 1})
        _record_event(db, retry_task_id, row["worker_id"], "task_queued",
                      from_status=None, to_status="queued", occurred_at=now,
                      detail={"retry_of_task_id": task_id, "retry_attempt": 1})
    return {"task_id": retry_task_id, "retry_of_task_id": task_id,
            "worker_id": row["worker_id"], "status": "queued",
            "retried": True, "retry_attempt": 1, "retry_limit": 1,
            "execution_mode": "manual_retry_new_task"}

def _persist_research_learning_candidate(task_id: str, worker_id: str, evaluation: dict) -> dict:
    """Store deterministic evaluation metrics as a reviewable memory note, not model training."""
    metrics = evaluation.get("metrics") if isinstance(evaluation, dict) else None
    if not isinstance(metrics, dict):
        return {"status": "skipped", "reason": "evaluation_metrics_missing"}
    try:
        from .worker_memory import append_memory
        memory = append_memory(
            worker_id,
            "validation_result",
            {
                "record_type": "research_quality_learning_candidate",
                "task_id": task_id,
                "evaluation_type": evaluation.get("evaluation_type", "deterministic_research_traceability_check"),
                "metrics": metrics,
                "learning_boundary": "metrics_only_no_claim_truth_or_strategy_learning",
                "review_required": True,
            },
            source_refs=[f"research_task:{task_id}"],
            quality_status="partial",
        )
        return {"status": "persisted_review_candidate", "memory_id": memory["memory_id"]}
    except Exception as exc:
        # Memory is an optional sidecar: it must not invalidate a completed task.
        return {"status": "not_persisted", "error_type": type(exc).__name__}

def classify_research_task_failure(error: Exception) -> dict:
    """Classify likely transient failures for operator review; never auto-retry."""
    error_type = type(error).__name__
    message = str(error).lower()
    transient_types = {
        "TimeoutError", "ConnectionError", "TemporaryError", "RateLimitError",
        "ServiceUnavailableError", "HTTPError",
    }
    transient_markers = ("timeout", "timed out", "temporarily unavailable",
                         "rate limit", "connection reset", "connection refused",
                         "service unavailable", "429", "502", "503", "504")
    likely_transient = error_type in transient_types or any(
        marker in message for marker in transient_markers
    )
    return {
        "failure_class": "transient_candidate" if likely_transient else "non_transient_candidate",
        "error_type": error_type,
        "retry_recommendation": "operator_review" if likely_transient else "inspect_before_retry",
        "automatic_retry": False,
    }

def execute_queued_research_task(task_id: str) -> bool:
    """Execute one persisted queued task; safe to call from FastAPI BackgroundTasks."""
    with _connect() as db:
        row = db.execute("SELECT * FROM analytical_agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None or row["status"] != "queued":
            return False
        # Claim atomically so duplicate dispatches cannot execute the same queued row.
        now = datetime.now(timezone.utc).isoformat()
        execution_token = str(uuid.uuid4())
        claimed = db.execute(
            "UPDATE analytical_agent_tasks SET status='running',updated_at=?,"
            "execution_attempts=execution_attempts+1,execution_token=? "
            "WHERE task_id=? AND status='queued'",
            (now, execution_token, task_id),
        )
        if claimed.rowcount != 1:
            return False
        _record_event(db, task_id, row["worker_id"], "task_claimed",
                      from_status="queued", to_status="running", occurred_at=now)
        task_input = json.loads(row["input_json"])
        agent_id = row["worker_id"]
    scope_token = None
    try:
        # Scope setup is part of execution: if it fails, the claimed task must
        # still be finalized as failed rather than stranded in the running state.
        scope_token = set_agent_scope(agent_id, task_id)
        # Build context inside the guarded execution block. A memory/configuration
        # failure must transition the claimed task to failed, not strand it as running.
        brain = brain_config(agent_id)
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
        learning_candidate = {"status": "not_created"}
        if evaluation is not None:
            _persist_quality_evaluation(task_id, agent_id, evaluation)
            if evaluation.get("status") != "invalid_input":
                learning_candidate = _persist_research_learning_candidate(task_id, agent_id, evaluation)
        result = {"agent_id": agent_id, "brain_context_sha256": row["brain_context_sha256"],
                  "research_learning_candidate": learning_candidate,
                  "brief": task_input["brief"], "input_data_received": task_input["data"] is not None,
                  "shared_core_result": synthesis,
                  "research_quality_evaluation": evaluation,
                  "research_quality_evaluation_status": evaluation_status,
                  "result_mode": "shared_core_synthesis" if synthesis.get("status") == "completed" else "provider_unavailable_or_not_configured",
                  "research_boundary": "supplied_data_only_no_live_market_fetch"}
        status = "completed"
    except Exception as exc:
        failure = classify_research_task_failure(exc)
        result = {"error": "Research task failed safely.", **failure}
        status = "failed"
    finally:
        if scope_token is not None:
            reset_agent_scope(scope_token)
    updated = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        # Fence completion by the exact claim token. If stale recovery requeued
        # this task and another dispatcher claimed it, the old executor must not
        # overwrite the newer attempt's result or append a misleading event.
        finalized = db.execute(
            "UPDATE analytical_agent_tasks SET status=?,result_json=?,updated_at=?,"
            "execution_token=NULL WHERE task_id=? AND status='running' AND execution_token=?",
            (status, _json(result), updated, task_id, execution_token),
        )
        if finalized.rowcount != 1:
            return False
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
        # Acquire the SQLite write reservation before selecting stale rows.
        # This prevents concurrent recovery callers from both observing the
        # same interrupted task and appending duplicate requeue audit events.
        db.execute("BEGIN IMMEDIATE")
        stale = db.execute(
            "SELECT task_id,worker_id,execution_attempts FROM analytical_agent_tasks "
            "WHERE status='running' AND updated_at < ?",
            (cutoff,),
        ).fetchall()
        requeued = []
        exhausted = []
        for task in stale:
            if task["execution_attempts"] >= MAX_TASK_EXECUTION_ATTEMPTS:
                failure = {
                    "error": "Research task stopped after reaching the execution attempt limit.",
                    "error_type": "ExecutionAttemptLimit",
                    "max_execution_attempts": MAX_TASK_EXECUTION_ATTEMPTS,
                }
                changed = db.execute(
                    "UPDATE analytical_agent_tasks SET status='failed',result_json=?,updated_at=?,"
                    "execution_token=NULL WHERE task_id=? AND status='running'",
                    (_json(failure), now, task["task_id"]),
                )
                if changed.rowcount == 1:
                    exhausted.append(task["task_id"])
                    _record_event(
                        db, task["task_id"], task["worker_id"], "task_failed",
                        from_status="running", to_status="failed", occurred_at=now,
                        detail={"reason": "execution_attempt_limit",
                                "execution_attempts": task["execution_attempts"]},
                    )
            else:
                changed = db.execute(
                    "UPDATE analytical_agent_tasks SET status='queued',updated_at=?,execution_token=NULL "
                    "WHERE task_id=? AND status='running'",
                    (now, task["task_id"]),
                )
                if changed.rowcount == 1:
                    requeued.append(task["task_id"])
                    _record_event(
                        db, task["task_id"], task["worker_id"], "task_requeued",
                        from_status="running", to_status="queued", occurred_at=now,
                        detail={"reason": "stale_recovery", "stale_after_seconds": stale_after_seconds,
                                "execution_attempts": task["execution_attempts"]},
                    )
        still_running = db.execute(
            "SELECT COUNT(*) FROM analytical_agent_tasks WHERE status='running'"
        ).fetchone()[0]
        queued = db.execute(
            "SELECT task_id FROM analytical_agent_tasks WHERE status='queued' ORDER BY created_at"
        ).fetchall()
    return {
        "requeued_interrupted_count": len(requeued),
        "failed_attempt_limit_count": len(exhausted),
        "failed_attempt_limit_task_ids": exhausted,
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

    # The configured core sees only supplied user data and the agent's role.
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
    return {
        "task_id": row["task_id"], "agent_id": row["worker_id"], "worker_id": row["worker_id"],
        "task_type": row["task_type"], "status": row["status"],
        "execution_attempts": row["execution_attempts"],
        "input": json.loads(row["input_json"]), "result": json.loads(row["result_json"]),
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


def agent_task_performance(agent_id: str | None = None, limit: int = 550) -> dict:
    """Summarize persisted task outcomes per worker; metrics are descriptive, not a skill score."""
    if agent_id is not None:
        brain_config(agent_id)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 550:
        raise ValueError("limit must be between 1 and 550")
    with _connect() as db:
        if agent_id is None:
            rows = db.execute(
                """SELECT worker_id,status,COUNT(*) AS count
                   FROM analytical_agent_tasks GROUP BY worker_id,status"""
            ).fetchall()
            total = db.execute("SELECT COUNT(*) FROM analytical_agent_tasks").fetchone()[0]
        else:
            rows = db.execute(
                """SELECT worker_id,status,COUNT(*) AS count
                   FROM analytical_agent_tasks WHERE worker_id=?
                   GROUP BY worker_id,status""", (agent_id,)
            ).fetchall()
            total = db.execute(
                "SELECT COUNT(*) FROM analytical_agent_tasks WHERE worker_id=?", (agent_id,)
            ).fetchone()[0]
        attempt_rows = db.execute(
            """SELECT worker_id,COALESCE(SUM(execution_attempts),0) AS execution_attempts,
                      COUNT(*) AS task_count
               FROM analytical_agent_tasks GROUP BY worker_id"""
        ).fetchall() if agent_id is None else db.execute(
            """SELECT worker_id,COALESCE(SUM(execution_attempts),0) AS execution_attempts,
                      COUNT(*) AS task_count
               FROM analytical_agent_tasks WHERE worker_id=? GROUP BY worker_id""",
            (agent_id,)
        ).fetchall()
        failure_rows = db.execute(
            "SELECT worker_id,result_json FROM analytical_agent_tasks WHERE status='failed'"
        ).fetchall() if agent_id is None else db.execute(
            "SELECT worker_id,result_json FROM analytical_agent_tasks WHERE status='failed' AND worker_id=?",
            (agent_id,)
        ).fetchall()
        recent = db.execute(
            """SELECT worker_id,status,COUNT(*) AS count
               FROM (SELECT worker_id,status FROM analytical_agent_tasks
                     ORDER BY updated_at DESC LIMIT ?)
               GROUP BY worker_id,status""", (limit,)
        ).fetchall() if agent_id is None else db.execute(
            """SELECT worker_id,status,COUNT(*) AS count
               FROM (SELECT worker_id,status FROM analytical_agent_tasks
                     WHERE worker_id=? ORDER BY updated_at DESC LIMIT ?)
               GROUP BY worker_id,status""", (agent_id, limit)
        ).fetchall()
    def summarize(grouped_rows):
        result = {}
        for row in grouped_rows:
            item = result.setdefault(row["worker_id"], {
                "agent_id": row["worker_id"], "task_count": 0,
                "queued": 0, "running": 0, "completed": 0, "failed": 0,
            })
            item[row["status"]] = row["count"]
            item["task_count"] += row["count"]
        for item in result.values():
            finished = item["completed"] + item["failed"]
            item["finished_count"] = finished
            item["completion_rate"] = round(item["completed"] / finished, 4) if finished else None
            item["failure_rate"] = round(item["failed"] / finished, 4) if finished else None
        return result
    all_agents = summarize(rows)
    recent_agents = summarize(recent)
    attempt_totals = {row["worker_id"]: row["execution_attempts"] for row in attempt_rows}
    failure_classes = {}
    for row in failure_rows:
        try:
            result = json.loads(row["result_json"])
        except (TypeError, ValueError):
            result = {}
        failure_class = result.get("failure_class", "unclassified")
        worker = row["worker_id"]
        bucket = failure_classes.setdefault(worker, {})
        bucket[failure_class] = bucket.get(failure_class, 0) + 1
    for worker, item in all_agents.items():
        attempts = attempt_totals.get(worker, 0)
        item["execution_attempts_total"] = attempts
        item["average_execution_attempts_per_task"] = round(attempts / item["task_count"], 4) if item["task_count"] else 0
        item["failure_class_counts"] = failure_classes.get(worker, {})
    return {
        "agent_id": agent_id,
        "task_count": total,
        "agents": all_agents,
        "recent_window_limit": limit,
        "recent_agents": recent_agents,
        "metric_definition": "completed/(completed+failed); queued/running excluded; descriptive historical task outcomes only",
        "performance_boundary": "not a capability or intelligence score; no autonomous ranking or live trading",
    }


def agent_research_quality_performance(agent_id: str | None = None, limit: int = 550) -> dict:
    """Aggregate persisted structural traceability metrics; never score factual correctness."""
    import math

    if agent_id is not None:
        brain_config(agent_id)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 550:
        raise ValueError("limit must be between 1 and 550")
    with _connect() as db:
        if agent_id is None:
            rows = db.execute(
                """SELECT worker_id,evaluation_json,created_at FROM research_quality_evaluations
                   ORDER BY created_at DESC LIMIT ?""", (limit,)
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT worker_id,evaluation_json,created_at FROM research_quality_evaluations
                   WHERE worker_id=? ORDER BY created_at DESC LIMIT ?""", (agent_id, limit)
            ).fetchall()
    agents = {}
    invalid_count = 0
    for row in rows:
        try:
            evaluation = json.loads(row["evaluation_json"])
            metrics = evaluation.get("metrics") if isinstance(evaluation, dict) else None
            if not isinstance(metrics, dict):
                invalid_count += 1
                continue
            values = {}
            for key in ("claim_reference_coverage", "known_source_reference_coverage"):
                value = metrics.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1:
                    values[key] = float(value)
            if not values:
                invalid_count += 1
                continue
        except (TypeError, ValueError):
            invalid_count += 1
            continue
        item = agents.setdefault(row["worker_id"], {
            "agent_id": row["worker_id"], "evaluation_count": 0,
            "claim_reference_coverage_sum": 0.0, "claim_reference_coverage_count": 0,
            "known_source_reference_coverage_sum": 0.0, "known_source_reference_coverage_count": 0,
        })
        item["evaluation_count"] += 1
        for key, value in values.items():
            sum_key = key + "_sum"
            count_key = key + "_count"
            item[sum_key] += value
            item[count_key] += 1
    for item in agents.values():
        for key in ("claim_reference_coverage", "known_source_reference_coverage"):
            count = item[key + "_count"]
            item[key + "_mean"] = round(item[key + "_sum"] / count, 4) if count else None
            item.pop(key + "_sum")
    return {
        "agent_id": agent_id,
        "evaluations_examined": len(rows),
        "invalid_or_unusable_evaluation_count": invalid_count,
        "agents": agents,
        "metric_definition": "mean structural source-reference coverage across stored evaluations; values with null or invalid metrics are excluded per metric",
        "quality_boundary": "does not establish source authenticity, entailment, factual accuracy, intelligence, or trading performance",
    }


def agent_supervisor_recommendations(agent_id: str | None = None, limit: int = 550) -> dict:
    """Return conservative, reviewable workflow suggestions from persisted metrics only."""
    task_metrics = agent_task_performance(agent_id=agent_id, limit=limit)
    quality_metrics = agent_research_quality_performance(agent_id=agent_id, limit=limit)
    recommendations = []
    task_agents = task_metrics["agents"]
    quality_agents = quality_metrics["agents"]
    agent_ids = sorted(set(task_agents) | set(quality_agents))
    for worker_id in agent_ids:
        tasks = task_agents.get(worker_id, {})
        quality = quality_agents.get(worker_id, {})
        finished = tasks.get("finished_count", 0)
        eval_count = quality.get("evaluation_count", 0)
        failure_rate = tasks.get("failure_rate")
        known_coverage = quality.get("known_source_reference_coverage_mean")
        if finished >= 5 and failure_rate is not None and failure_rate >= 0.30:
            recommendations.append({
                "agent_id": worker_id,
                "priority": "review",
                "reason_code": "repeated_task_failures",
                "evidence": {"finished_tasks": finished, "failure_rate": failure_rate},
                "suggested_action": "Inspect recent task failure types and input/provider availability before assigning more tasks.",
            })
        if eval_count >= 3 and known_coverage is not None and known_coverage < 0.70:
            recommendations.append({
                "agent_id": worker_id,
                "priority": "review",
                "reason_code": "low_source_reference_coverage",
                "evidence": {"evaluations": eval_count, "mean_known_source_reference_coverage": known_coverage},
                "suggested_action": "Review source registry completeness and claim-to-source mapping in the research workflow.",
            })
        if finished >= 5 and failure_rate is not None and failure_rate <= 0.10 and eval_count >= 3 and known_coverage is not None and known_coverage >= 0.90:
            recommendations.append({
                "agent_id": worker_id,
                "priority": "observe",
                "reason_code": "consistent_structural_traceability",
                "evidence": {"finished_tasks": finished, "failure_rate": failure_rate,
                             "evaluations": eval_count, "mean_known_source_reference_coverage": known_coverage},
                "suggested_action": "Consider this workflow as a candidate for a controlled offline benchmark; do not auto-promote it.",
            })
    return {
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "source": "persisted_task_outcomes_and_structural_traceability_metrics",
        "decision_mode": "advisory_only",
        "minimum_evidence": {"finished_tasks": 5, "quality_evaluations": 3},
        "limitations": [
            "No autonomous task reassignment, agent ranking, code changes, or deployment.",
            "Task completion and source-reference coverage are proxies, not measures of intelligence or factual correctness.",
            "Review recommendations against underlying records before acting.",
        ],
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
        return {"selected": 0, "dispatched": 0, "max_concurrency": max_concurrency,
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
    dispatch_errors = []
    with ThreadPoolExecutor(max_workers=min(max_concurrency, len(task_ids)),
                            thread_name_prefix="market-mind-supervisor") as pool:
        futures = {pool.submit(execute_queued_research_task, task_id): task_id for task_id in task_ids}
        for future in as_completed(futures):
            task_id = futures[future]
            try:
                executed = future.result()
                if executed:
                    completed.append(task_id)
            except Exception as exc:
                # One task failure must not interrupt dispatch of sibling tasks.
                dispatch_errors.append({"task_id": task_id, "error_type": type(exc).__name__})
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
    return {
        "selected": len(task_ids),
        "dispatched": len(completed),
        "max_concurrency": min(max_concurrency, len(task_ids)),
        "status": "completed",
        "task_ids": task_ids,
        "dispatch_error_count": len(dispatch_errors),
        "dispatch_errors": dispatch_errors,
        "dispatch_mode": "bounded_process_local_queue_snapshot",
        "note": "Tasks are persisted in SQLite; dispatch is explicit and process-local, not a continuously running distributed supervisor.",
    }
