"""Optional Zulip communication adapter for MARKET-MIND-AI.

This is a THIN COMMUNICATION LAYER, not a second intelligence platform:

* The 550-agent registry, task queue, research message bus, memory and market
  data systems remain authoritative and completely unchanged.
* This module only *consumes* existing outputs (task activity, agent messages,
  health/CI summaries) and maps them to fixed Zulip streams and topics.
* Inbound Zulip messages are NEVER executable commands. This module does not
  read them at all in this phase; no code, orders or provider actions can be
  triggered from a chat message.
* With no ``ZULIP_*`` configuration the adapter is a complete no-op, so the
  terminal, agents and ingestion continue normally offline.

Security design:
- Credentials come only from environment variables (backend process).
- Secrets are never returned, logged, placed in agent prompts or memory, or
  sent to the frontend. Only a redacted ``configured: true/false`` is exposed.
- Egress is restricted to a fixed, validated base URL (https required unless
  explicitly loopback for local testing); no caller-supplied URL is accepted.
- Streams and topics are allowlisted constants; no arbitrary channel targeting.
- Deliveries are idempotent: a bounded SQLite table records message keys so a
  retry never duplicates a notification.
- Failures queue notifications locally and are retried with bounded backoff;
  a Zulip outage never blocks research or ingestion.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from . import sqlite_tuning
from .audit_events import redact as _redact_value


def redact_text(value: str) -> str:
    """Reuse the existing audit redactor for outbound text."""
    result = _redact_value(value)
    return result if isinstance(result, str) else str(result)

TIMEOUT_SECONDS = 5.0
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 0.5
MAX_PAYLOAD_CHARS = 4000
MAX_QUEUE = 500

# Fixed stream/topic structure. A caller can select from these only.
STREAMS: dict[str, tuple[str, ...]] = {
    "market-data": (
        "US-stocks", "India-NSE-BSE", "Forex", "Cryptocurrency", "Gold",
        "Provider-health", "Data-quality",
    ),
    "agent-research": (
        "Research-assignments", "Research-results", "Agent-findings",
        "Cross-market-analysis", "Research-review", "Agent-errors",
    ),
    "system-operations": (
        "Backend-health", "Frontend-health", "Worker-status",
        "Database-health", "Memory-system", "Service-recovery",
    ),
    "ci-testing": (
        "GitHub-Actions", "Backend-tests", "Frontend-tests",
        "Security-scans", "Build-results", "Release-readiness",
    ),
    "risk-governance": (
        "Data-provenance", "Permission-events", "Security-alerts",
        "Audit-events", "Policy-violations",
    ),
}

DATA_STATUS_LABELS = ("LIVE", "DELAYED", "HISTORICAL", "SYNTHETIC", "UNAVAILABLE")


class ZulipConfigError(ValueError):
    """Raised for invalid optional configuration; never contains secret values."""


def _db_path() -> Path:
    return Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))


def _connect() -> sqlite3.Connection:
    connection = sqlite_tuning.connect(_db_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS zulip_notifications (
            dedupe_key TEXT PRIMARY KEY,
            stream TEXT NOT NULL,
            topic TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_error_type TEXT
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_zulip_status ON zulip_notifications(status, created_at)"
    )
    return connection


def config() -> dict[str, Any]:
    """Return redacted configuration state; never returns the API key."""
    site = os.getenv("ZULIP_SITE_URL", "").strip().rstrip("/")
    bot_email = os.getenv("ZULIP_BOT_EMAIL", "").strip()
    key = os.getenv("ZULIP_API_KEY", "").strip()
    configured = bool(site and bot_email and key)
    issues = []
    if site:
        parts = urlsplit(site)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            issues.append("invalid_site_url")
        elif parts.scheme == "http" and parts.hostname not in {"127.0.0.1", "localhost"}:
            issues.append("plaintext_site_url")
    return {
        "configured": configured,
        "site_configured": bool(site),
        "bot_configured": bool(bot_email),
        "api_key_configured": bool(key),
        "enabled": configured and not issues,
        "issues": issues,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_retries": MAX_RETRIES,
        "streams": {name: list(topics) for name, topics in STREAMS.items()},
        "data_status_labels": list(DATA_STATUS_LABELS),
        "credentials_exposed": False,
        "inbound_commands_enabled": False,
        "broker_execution": False,
        "real_money": False,
    }


def _endpoint() -> str:
    site = os.getenv("ZULIP_SITE_URL", "").strip().rstrip("/")
    if not site:
        raise ZulipConfigError("Zulip is not configured")
    parts = urlsplit(site)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ZulipConfigError("invalid Zulip site URL")
    if parts.scheme == "http" and parts.hostname not in {"127.0.0.1", "localhost"}:
        raise ZulipConfigError("Zulip site URL must use HTTPS")
    return site + "/api/v1/messages"


def validate_target(stream: str, topic: str) -> None:
    if stream not in STREAMS:
        raise ValueError("stream is not allowlisted")
    if topic not in STREAMS[stream]:
        raise ValueError("topic is not allowlisted for this stream")


def _sanitize(value: Any) -> Any:
    """Redact secrets and bound size before anything leaves the process."""
    if isinstance(value, str):
        cleaned = redact_text(value)
        # Redact inline credential-shaped assignments in free text.
        import re

        cleaned = re.sub(
            r"(?i)\b(token|api[_-]?key|password|secret|authorization)\b\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            cleaned,
        )
        return cleaned[:MAX_PAYLOAD_CHARS]
    if isinstance(value, dict):
        return {str(key)[:80]: _sanitize(item) for key, item in list(value.items())[:50]}
    if isinstance(value, list):
        return [_sanitize(item) for item in value[:50]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:MAX_PAYLOAD_CHARS]


def _dedupe_key(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_message(
    *,
    stream: str,
    topic: str,
    message_type: str,
    data_status: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
    task_id: str | None = None,
    market: str | None = None,
    evidence: list[str] | None = None,
    source: str | None = None,
    content: str = "",
) -> dict[str, Any]:
    """Build a validated, provenance-typed Zulip message payload."""
    validate_target(stream, topic)
    if data_status not in DATA_STATUS_LABELS:
        raise ValueError("data_status must be a verified status label")
    if not content.strip():
        raise ValueError("content must not be empty")
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "source": "MARKET-MIND-AI",
        "mode": "research_only",
        "stream": stream,
        "topic": topic,
        "message_type": message_type,
        "data_status": data_status,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "task_id": task_id,
        "market": market,
        "evidence_refs": list(evidence or [])[:20],
        "source_attribution": source,
        "timestamp": now,
        "content": content[:MAX_PAYLOAD_CHARS],
    }
    payload["dedupe_key"] = _dedupe_key(payload)
    return _sanitize(payload)


def _deliver(payload: dict[str, Any]) -> dict[str, Any]:
    """One bounded HTTP POST; secrets are used only as request parameters."""
    endpoint = _endpoint()
    bot_email = os.getenv("ZULIP_BOT_EMAIL", "").strip()
    key = os.getenv("ZULIP_API_KEY", "").strip()
    form = {
        "type": "stream",
        "to": payload["stream"],
        "topic": payload["topic"],
        "content": "[" + payload["data_status"] + "] " + payload["content"],
    }
    last_error = "unknown"
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = httpx.post(
                endpoint, data=form, auth=(bot_email, key),
                timeout=TIMEOUT_SECONDS,
            )
            if response.status_code in {200, 201}:
                return {"status": "sent", "attempts": attempt + 1}
            if response.status_code in {429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After")
                delay = min(float(retry_after) if retry_after and retry_after.isdigit()
                            else RETRY_DELAY_SECONDS * (2 ** attempt), 30.0)
                time.sleep(delay)
                last_error = f"http_{response.status_code}"
                continue
            return {"status": "rejected", "http_status": response.status_code,
                    "attempts": attempt + 1}
        except (httpx.HTTPError, ValueError, OSError) as exc:
            last_error = type(exc).__name__
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
                continue
    return {"status": "delivery_failed", "error_type": last_error,
            "attempts": MAX_RETRIES + 1}


def publish(payload: dict[str, Any]) -> dict[str, Any]:
    """Idempotently publish one validated message; queue on any failure.

    A Zulip outage never raises into the caller's research path. The existing
    backend database remains the source of truth for all task state.
    """
    if not config()["enabled"]:
        return {"status": "disabled", "dedupe_key": payload.get("dedupe_key")}
    key = payload.get("dedupe_key") or _dedupe_key(payload)
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        existing = db.execute(
            "SELECT status FROM zulip_notifications WHERE dedupe_key=?", (key,)
        ).fetchone()
        if existing and existing["status"] == "sent":
            return {"status": "duplicate_suppressed", "dedupe_key": key}
        if existing is None:
            count = db.execute("SELECT COUNT(*) FROM zulip_notifications").fetchone()[0]
            if count >= MAX_QUEUE:
                return {"status": "queue_full", "dedupe_key": key}
            db.execute(
                "INSERT INTO zulip_notifications "
                "(dedupe_key, stream, topic, payload_json, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (key, payload["stream"], payload["topic"],
                 json.dumps(payload, sort_keys=True), now),
            )
    result = _deliver(payload)
    with _connect() as db:
        if result["status"] == "sent":
            db.execute("UPDATE zulip_notifications SET status='sent' WHERE dedupe_key=?", (key,))
        else:
            db.execute(
                "UPDATE zulip_notifications SET status='queued', last_error_type=? "
                "WHERE dedupe_key=?", (result.get("error_type") or result["status"], key),
            )
    return {**result, "dedupe_key": key}


def flush_queue(limit: int = 20) -> dict[str, Any]:
    """Retry queued notifications with bounded work per call."""
    if not config()["enabled"]:
        return {"status": "disabled", "retried": 0}
    retried = sent = 0
    with _connect() as db:
        rows = db.execute(
            "SELECT dedupe_key, payload_json FROM zulip_notifications "
            "WHERE status='queued' ORDER BY created_at LIMIT ?", (limit,),
        ).fetchall()
    for row in rows:
        retried += 1
        result = _deliver(json.loads(row["payload_json"]))
        if result["status"] == "sent":
            sent += 1
            with _connect() as db:
                db.execute(
                    "UPDATE zulip_notifications SET status='sent', last_error_type=NULL "
                    "WHERE dedupe_key=?", (row["dedupe_key"],),
                )
    return {"status": "completed", "retried": retried, "sent": sent}


def status() -> dict[str, Any]:
    """Redacted health/status for the operations panel; no secrets included."""
    result = config()
    with _connect() as db:
        counts = {
            row["status"]: row["count"]
            for row in db.execute(
                "SELECT status, COUNT(*) AS count FROM zulip_notifications GROUP BY status"
            )
        }
    result.update({
        "pending_count": counts.get("queued", 0),
        "sent_count": counts.get("sent", 0),
        "queue_limit": MAX_QUEUE,
    })
    if counts.get("sent"):
        last = None
        with _connect() as db:
            row = db.execute(
                "SELECT created_at FROM zulip_notifications WHERE status='sent' "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            last = row["created_at"] if row else None
        result["last_successful_sync"] = last
    return result


def publish_research_update(
    *, stream: str, topic: str, message_type: str, data_status: str,
    source: str, content: str, **fields: Any,
) -> dict[str, Any]:
    """Convenience wrapper used by existing task/market notification seams."""
    return publish(build_message(
        stream=stream, topic=topic, message_type=message_type,
        data_status=data_status, source=source, content=content, **fields,
    ))


def notify_task_result(task: dict[str, Any]) -> dict[str, Any]:
    """Map an EXISTING completed/failed task record to a Zulip notification.

    Called as a best-effort side effect only; the task database is authoritative
    and this function never mutates it or blocks its execution path.
    """
    status = str(task.get("status") or "")
    if status not in {"completed", "failed"}:
        return {"status": "skipped"}
    topic = "Research-results" if status == "completed" else "Agent-errors"
    try:
        payload = build_message(
            stream="agent-research", topic=topic,
            message_type=f"task_{status}",
            data_status="HISTORICAL",
            agent_id=task.get("worker_id"),
            task_id=task.get("task_id"),
            source="existing_analytical_agent_tasks",
            content=(
                f"Research task {task.get('task_id')} ({task.get('worker_id')}) "
                f"finished with status {status}."
            ),
            evidence=[task.get("task_id")],
        )
        return publish(payload)
    except Exception:  # noqa: BLE001 - never break the task
        return {"status": "notification_error", "authoritative_state_unchanged": True}


def notify_market_message(message: dict[str, Any]) -> dict[str, Any]:
    """Map an EXISTING internal research-bus message to a Zulip notification."""
    group = str(message.get("market_group") or "")
    topic_by_group = {
        "us": "US-stocks", "india": "India-NSE-BSE",
        "forex": "Forex", "crypto": "Cryptocurrency",
    }
    topic = topic_by_group.get(group)
    if topic is None:
        return {"status": "skipped"}
    try:
        return publish(build_message(
            stream="market-data", topic=topic,
            message_type="research_note", data_status="HISTORICAL",
            agent_id=message.get("agent_id"),
            market=group,
            source="existing_agent_network",
            content=str(message.get("topic") or "Research note"),
            evidence=list(message.get("source_refs") or []),
        ))
    except Exception:  # noqa: BLE001
        return {"status": "notification_error", "authoritative_state_unchanged": True}


def notify_daily_digest(cycle: dict[str, Any]) -> dict[str, Any]:
    """Publish ONE consolidated daily research digest via the existing adapter.

    No per-agent messages are generated. The digest is best-effort: a Zulip
    outage is recorded in the queue and never interrupts the research cycle.
    """
    scorecard = cycle.get("quality_scorecard") or {}
    execution = cycle.get("execution") or {}
    topics = cycle.get("observation_topics") or {}
    lines = [
        f"Daily cycle {cycle.get('cycle_id')} — status {cycle.get('status') or 'in_progress'}",
        f"Observations: {scorecard.get('usable_observations', 0)} usable, "
        f"{scorecard.get('unavailable_observations', 0)} unavailable, "
        f"{scorecard.get('stale_observations', 0)} stale.",
        f"Agents: {execution.get('agents_executed_tasks', 0)} executed of "
        f"{execution.get('registered_agents', 0)} registered profiles "
        "(profiles are not independent models).",
        f"Tasks: {execution.get('tasks_completed', 0)} completed, "
        f"{execution.get('tasks_pending', 0)} pending.",
    ]
    for group in cycle.get("observations") or []:
        lines.append(
            f"{group.get('market_group')}: {group.get('data_status')} "
            f"({group.get('headline', '')})"
        )
    try:
        return publish(build_message(
            stream="agent-research", topic="Research-review",
            message_type="daily_digest", data_status="HISTORICAL",
            source="existing_daily_intelligence_cycle",
            content="\n".join(lines)[:MAX_PAYLOAD_CHARS],
            task_id=cycle.get("cycle_id"),
            evidence=[cycle.get("cycle_id")],
        ))
    except Exception:  # noqa: BLE001 - communication must never break research
        return {"status": "notification_error", "authoritative_state_unchanged": True}
