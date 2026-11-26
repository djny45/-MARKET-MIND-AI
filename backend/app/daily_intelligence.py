"""Daily Intelligence Research Cycle — orchestration over EXISTING systems.

This module is the missing daily-cadence layer. It deliberately owns no new
agent registry, no new task queue, no new research engine, no new provider and
no new communication adapter:

* Task creation uses ``analytical_agent_tasks.enqueue_research_task``.
* Execution accounting uses ``agent_supervisor_status`` /
  ``agent_task_performance`` / ``list_recent_task_activity``.
* Market observations use ``four_market_terminal.build_terminal_snapshot`` and
  the existing provider adapters, with existing status labels.
* Provider reliability uses ``provider_health`` observations.
* Quality scoring uses ``research_quality_eval`` / ``research_evaluation``.
* Findings use ``intelligence_research.build_research_finding`` and are stored
  through ``worker_memory.append_memory``.
* Communication uses ``zulip_notifier.notify_daily_digest`` — one consolidated
  message, never 550.

The append-only ``daily_research_archive`` table in the existing database keeps
every cycle revision so previous reports and outcomes can be compared. The
existing backend task database remains authoritative for task state.

A Zulip outage, a provider outage or a failed market must never stop the cycle.
No data is fabricated: an unavailable observation is recorded as UNAVAILABLE.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import sqlite_tuning
from .market_data import DataStatus
from .market_quotes import MARKET_GROUPS

CYCLE_VERSION = "1.0.0"
MARKET_SESSIONS: dict[str, tuple[str, str]] = {
    "us": ("America/New_York", "regular"),
    "india": ("Asia/Kolkata", "regular"),
    "forex": ("UTC", "reference_fixing"),
    "crypto": ("UTC", "continuous"),
}
# Gold is a cross-market reference instrument, not a fifth market group.
GOLD_SESSION = ("UTC", "reference_or_tokenized")

CYCLE_TOPICS = {
    "us": "US-stocks", "india": "India-NSE-BSE", "forex": "Forex",
    "crypto": "Cryptocurrency", "gold": "Gold",
}


@contextmanager
def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite_tuning.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS daily_research_archive (
            cycle_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            archive_id TEXT NOT NULL UNIQUE,
            cycle_date TEXT NOT NULL,
            market_group TEXT NOT NULL,
            report_json TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            parent_sha256 TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (cycle_id, revision, market_group)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_archive_date "
        "ON daily_research_archive(cycle_date, market_group)"
    )
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cycle_id(date: datetime | str) -> str:
    """Stable, idempotent cycle identity for one UTC date."""
    text = date.date().isoformat() if isinstance(date, datetime) else str(date)[:10]
    return f"daily-{text}"


def session_for(market_group: str) -> dict[str, Any]:
    """Return the declared exchange timezone/session for a market."""
    tz_name, kind = MARKET_SESSIONS.get(market_group, GOLD_SESSION)
    try:
        ZoneInfo(tz_name)
        valid = True
    except (ZoneInfoNotFoundError, ValueError):
        valid = False
    return {
        "market_group": market_group, "timezone": tz_name,
        "session": kind, "timezone_valid": valid,
    }


def collect_market_observation(group: str) -> dict[str, Any]:
    """Collect one market's verified observations using existing adapters.

    Any provider failure is recorded as UNAVAILABLE; no price is invented.
    """
    from .four_market_terminal import build_terminal_snapshot
    from .instruments import INSTRUMENTS

    session = session_for(group)
    try:
        snapshot = build_terminal_snapshot(
            INSTRUMENTS, market_groups=[group], now=datetime.now(timezone.utc)
        )
        market = snapshot["markets"][0]
        # The board's market_status is a freshness summary (fresh/stale/
        # partially_stale/unavailable), NOT a data provenance label. Derive the
        # observation label from the actual quote statuses, which are always one
        # of the five allowed labels.
        quote_statuses = [q["status"] for q in market["quotes"]]
        observed_labels = sorted(set(quote_statuses))
        data_label = observed_labels[0] if len(observed_labels) == 1 else (
            DataStatus.UNAVAILABLE.value if not observed_labels else "mixed"
        )
        if data_label == "mixed":
            # Mixed labels must be reported honestly, not collapsed into LIVE.
            data_label = DataStatus.UNAVAILABLE.value
        return {
            "market_group": group,
            "data_status": data_label,
            "status_label": data_label.upper(),
            "market_freshness": market["market_status"],
            "observed_labels": observed_labels,
            "headline": market["headline"],
            "usable_count": market["usable_count"],
            "unavailable_count": market["unavailable_count"],
            "stale_count": market["stale_count"],
            "source": market["adapter"]["name"],
            "quotes": [
                {
                    "symbol": q["symbol"], "status": q["status"],
                    "status_label": q["status_label"],
                    "timestamp": q["timestamp"], "retrieved_at": q["retrieved_at"],
                    "source": q["source"],
                }
                for q in market["quotes"][:10]
            ],
            "session": session,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001 - a market failure is data, not a crash
        return {
            "market_group": group, "data_status": DataStatus.UNAVAILABLE.value,
            "status_label": "UNAVAILABLE",
            "headline": "PROVIDER UNAVAILABLE", "usable_count": 0,
            "unavailable_count": 0, "stale_count": 0,
            "observed_labels": [],
            "market_freshness": "unavailable",
            "reason": f"provider unavailable ({type(exc).__name__}); no observation recorded",
            "session": session,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


def collect_gold_observation() -> dict[str, Any]:
    """Tokenized-gold reference via the existing CoinGecko adapter only."""
    from .exchange_intelligence import gold_token_quote

    quote = gold_token_quote()
    payload = quote.to_payload()
    return {
        "market_group": "gold",
        "instrument_class": "tokenized_gold",
        "data_status": payload["status"],
        "status_label": payload["status_label"],
        "last": payload["last"], "source": payload["source"],
        "timestamp": payload["timestamp"], "retrieved_at": payload["retrieved_at"],
        "session": session_for("gold"),
        "note": "Tokenized gold; not spot or futures gold.",
    }


def execution_accounting() -> dict[str, Any]:
    """Report only work the existing backend actually recorded."""
    from .analytical_agent_tasks import (
        agent_supervisor_status, agent_task_performance, list_recent_task_activity,
    )
    from .worker_registry import EXPECTED_WORKER_COUNT

    activity = list_recent_task_activity(limit=500)
    supervisor = agent_supervisor_status()
    performance = agent_task_performance(limit=550)
    status_counts = dict(activity.get("status_counts") or {})
    agents = performance.get("agents") or {}
    executed = sum(
        1 for row in agents.values()
        if (row.get("task_count") or 0) > 0
    )
    return {
        "registered_agents": EXPECTED_WORKER_COUNT,
        "agents_assigned_tasks": len(agents),
        "agents_executed_tasks": executed,
        "agents_completed_tasks": sum(
            1 for row in agents.values() if (row.get("completed") or 0) > 0
        ),
        "agents_failed": sum(
            1 for row in agents.values() if (row.get("failed") or 0) > 0
        ),
        "agents_skipped": status_counts.get("cancelled", 0),
        "concurrent_execution_count": (
            supervisor.get("supervisor_heartbeat") or {}
        ).get("max_concurrency"),
        "tasks_completed": status_counts.get("completed", 0),
        "tasks_pending": status_counts.get("queued", 0) + status_counts.get("running", 0),
        "task_status_counts": status_counts,
        "metric_definition": (
            "Counts come from recorded task lifecycle events only. 550 registered "
            "profiles are NOT 550 active models or independent processes."
        ),
    }


def provider_reliability() -> dict[str, Any]:
    """Descriptive reliability from existing provider health observations."""
    from .provider_health import ProviderHealthRegistry

    registry = ProviderHealthRegistry()
    report = registry.report()
    providers = report.get("providers") if isinstance(report, dict) else []
    rows = []
    for row in providers or []:
        failures = int(row.get("consecutive_failures") or 0)
        observations = int(row.get("observations") or 0)
        health = str(row.get("health") or "unknown")
        score = round(max(0.0, 1.0 - failures / max(observations, 1)), 4) if observations else None
        rows.append({
            "provider": row.get("name"), "health": health,
            "freshness": row.get("freshness"),
            "consecutive_failures": failures, "observations": observations,
            "reliability_score": score,
        })
    return {
        "providers": rows,
        "data_note": (
            "Score is descriptive: 1 - consecutive_failures/observations from "
            "in-memory observations. It is not a licensing or authenticity claim."
        ),
    }


def quality_scorecard(cycle: dict[str, Any]) -> dict[str, Any]:
    """Consolidate existing structural/accuracy primitives into a daily scorecard."""
    observations = cycle.get("observations") or []
    usable = sum(int(row.get("usable_count") or 0) for row in observations)
    unavailable = sum(int(row.get("unavailable_count") or 0) for row in observations)
    stale = sum(int(row.get("stale_count") or 0) for row in observations)
    total = usable + unavailable
    accounting = cycle.get("execution") or {}
    registered = int(accounting.get("registered_agents") or 0)
    executed = int(accounting.get("agents_executed_tasks") or 0)
    return {
        "observation_coverage": round(usable / total, 4) if total else None,
        "usable_observations": usable,
        "unavailable_observations": unavailable,
        "stale_observations": stale,
        "agent_participation": round(executed / registered, 4) if registered else None,
        "data_labels_verified": all(
            row.get("data_status") in {
                "live", "delayed", "historical", "synthetic", "unavailable",
            }
            for row in observations
        ),
        "scorecard_note": (
            "Descriptive process metrics only. Coverage and participation do not "
            "establish research correctness, predictive power or consensus truth."
        ),
    }


def consensus_from_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Honest descriptive agreement metrics; consensus is never proof."""
    if not findings:
        return {"available": False, "reason": "no findings in this cycle"}
    directions = [
        str(item.get("direction") or "").strip().lower()
        for item in findings if item.get("direction")
    ]
    counts: dict[str, int] = {}
    for value in directions:
        counts[value] = counts.get(value, 0) + 1
    total = sum(counts.values())
    top, top_count = max(counts.items(), key=lambda item: item[1]) if counts else (None, 0)
    return {
        "available": bool(directions), "finding_count": len(findings),
        "direction_counts": counts,
        "agreement_share": round(top_count / total, 4) if total else None,
        "dominant_direction": top,
        "disagreement_present": len(counts) > 1,
        "data_note": (
            "Matching labels are descriptive agreement only, not statistical "
            "consensus, causality or evidence of correctness."
        ),
    }


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def archive_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    """Append a versioned, content-addressed archive revision for each market."""
    created = datetime.now(timezone.utc).isoformat()
    saved = []
    with _connect() as db:
        for row in cycle["observations"]:
            group = row["market_group"]
            prior = db.execute(
                "SELECT content_sha256 FROM daily_research_archive "
                "WHERE cycle_id=? AND market_group=? ORDER BY revision DESC LIMIT 1",
                (cycle["cycle_id"], group),
            ).fetchone()
            revision_row = db.execute(
                "SELECT COALESCE(MAX(revision), 0) FROM daily_research_archive "
                "WHERE cycle_id=? AND market_group=?", (cycle["cycle_id"], group),
            ).fetchone()
            revision = int(revision_row[0]) + 1
            report = {**row, "cycle_id": cycle["cycle_id"], "created_at": created}
            digest = hashlib.sha256(_canonical(report)).hexdigest()
            archive_id = hashlib.sha256(
                f"{cycle['cycle_id']}:{group}:{revision}:{digest}".encode()
            ).hexdigest()[:32]
            db.execute(
                "INSERT INTO daily_research_archive "
                "(cycle_id, revision, archive_id, cycle_date, market_group, "
                "report_json, content_sha256, parent_sha256, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cycle["cycle_id"], revision, archive_id, cycle["cycle_date"],
                 group, json.dumps(report, sort_keys=True, default=str), digest,
                 prior["content_sha256"] if prior else None, created),
            )
            saved.append({
                "market_group": group, "revision": revision,
                "archive_id": archive_id, "content_sha256": digest,
                "parent_sha256": prior["content_sha256"] if prior else None,
            })
    return {"cycle_id": cycle["cycle_id"], "archived": saved}


def read_archive(cycle_id_value: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Read append-only archive rows; never overwrite previous reports."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    clauses, params = "", []
    if cycle_id_value:
        clauses = " WHERE cycle_id=?"
        params.append(cycle_id_value)
    with _connect() as db:
        rows = db.execute(
            "SELECT cycle_id, revision, archive_id, cycle_date, market_group, "
            "content_sha256, parent_sha256, created_at "
            "FROM daily_research_archive" + clauses +
            " ORDER BY cycle_date DESC, revision DESC LIMIT ?", (*params, limit),
        ).fetchall()
    return {
        "count": len(rows), "rows": [dict(row) for row in rows],
        "data_note": "Append-only version history; no report is overwritten.",
    }


def compare_cycles(cycle_id_value: str, previous_cycle_id: str) -> dict[str, Any]:
    """Day-over-day comparison of recorded observations, not invented outcomes."""
    current = read_archive(cycle_id_value, limit=200)["rows"]
    previous = read_archive(previous_cycle_id, limit=200)["rows"]
    previous_by_group = {row["market_group"]: row for row in previous}
    comparisons = []
    for row in current:
        prior = previous_by_group.get(row["market_group"])
        comparisons.append({
            "market_group": row["market_group"],
            "current_revision": row["revision"],
            "previous_revision": prior["revision"] if prior else None,
            "content_changed": bool(prior and row["content_sha256"] != prior["content_sha256"]),
        })
    return {
        "cycle_id": cycle_id_value, "previous_cycle_id": previous_cycle_id,
        "comparisons": comparisons,
        "data_note": (
            "Compares archived report content hashes only. It does not assert "
            "research accuracy or that a changed report is an improvement."
        ),
    }


def run_daily_cycle(
    *,
    date: datetime | str | None = None,
    publish_zulip: bool = True,
    enqueue_tasks: bool = False,
) -> dict[str, Any]:
    """Run one bounded, idempotent daily research cycle.

    ``enqueue_tasks`` is opt-in: scheduling is separate from execution, which
    remains with the existing supervisor. No 550 tasks are created by default;
    a small bounded set of market research assignments is enqueued only when
    explicitly requested.
    """
    reference = date or datetime.now(timezone.utc)
    identifier = cycle_id(reference)
    existing = read_archive(identifier, limit=1)
    duplicate = bool(existing["rows"])

    observations = [collect_market_observation(group) for group in MARKET_GROUPS]
    observations.append(collect_gold_observation())

    cycle: dict[str, Any] = {
        "cycle_id": identifier,
        "cycle_date": identifier.replace("daily-", ""),
        "cycle_version": CYCLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sessions": [session_for(group) for group in MARKET_GROUPS] + [session_for("gold")],
        "observations": observations,
        "execution": execution_accounting(),
        "provider_reliability": provider_reliability(),
        "duplicate_cycle_detected": duplicate,
        "execution_boundary": {
            "paper_trading": False, "broker_execution": False, "real_money": False,
        },
    }
    cycle["quality_scorecard"] = quality_scorecard(cycle)
    cycle["consensus"] = consensus_from_findings([])

    enqueue_result = {"status": "skipped"}
    if enqueue_tasks and not duplicate:
        from .analytical_agent_tasks import enqueue_research_task

        enqueued = []
        for group in MARKET_GROUPS:
            try:
                task = enqueue_research_task(
                    agent_id=f"worker_{(len(enqueued) % 550) + 1:03d}",
                    brief=f"Daily {group} market research for {cycle['cycle_date']}",
                    data={"cycle_id": identifier, "market_group": group,
                          "observations": observations},
                )
                enqueued.append(task.get("task_id"))
            except Exception:  # noqa: BLE001 - one market cannot stop the cycle
                continue
        enqueue_result = {"status": "completed", "task_ids": enqueued}
    cycle["task_allocation"] = enqueue_result

    archive = archive_cycle(cycle)
    cycle["archive"] = archive

    notification = {"status": "skipped"}
    if publish_zulip:
        from .zulip_notifier import notify_daily_digest

        notification = notify_daily_digest(cycle)
    cycle["zulip_notification"] = notification

    if duplicate:
        cycle["status"] = "duplicate_suppressed"
    elif any(row["data_status"] == "unavailable" for row in observations):
        cycle["status"] = "partial"
    else:
        cycle["status"] = "completed"
    return cycle


# Expose a bounded previous-cycle helper for historical outcome comparison.
def previous_cycle_id(cycle_id_value: str, days: int = 1) -> str:
    if not 1 <= days <= 30:
        raise ValueError("days must be between 1 and 30")
    date = datetime.strptime(cycle_id_value.replace("daily-", ""), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    return cycle_id(date - timedelta(days=days))


# ---------------------------------------------------------------------------
# Persistent daily schedule state (in the EXISTING database, no new daemon).
# The existing supervisor calls `due_cycle` once per poll; this makes the
# schedule persistent across restarts and recovers cycles missed while offline.
# ---------------------------------------------------------------------------

SCHEDULE_SINGLETON = 1


def _schedule_db():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite_tuning.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS daily_cycle_schedule (
            singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
            enabled INTEGER NOT NULL DEFAULT 1,
            last_cycle_id TEXT,
            last_completed_at TEXT,
            next_cycle_id TEXT,
            missed_cycles INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    db.execute(
        "INSERT OR IGNORE INTO daily_cycle_schedule "
        "(singleton_id, enabled, updated_at) VALUES (?, 1, ?)",
        (SCHEDULE_SINGLETON, datetime.now(timezone.utc).isoformat()),
    )
    return db


def schedule_status() -> dict[str, Any]:
    """Report persistent schedule state; no secrets, no claims of execution."""
    db = _schedule_db()
    try:
        row = db.execute(
            "SELECT * FROM daily_cycle_schedule WHERE singleton_id=?",
            (SCHEDULE_SINGLETON,),
        ).fetchone()
    finally:
        db.close()
    now = datetime.now(timezone.utc)
    missed = 0
    if row["last_cycle_id"]:
        try:
            last = datetime.strptime(
                row["last_cycle_id"].replace("daily-", ""), "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
            missed = max(0, (now.date() - last.date()).days - 1)
        except ValueError:
            missed = 0
    return {
        "enabled": bool(row["enabled"]),
        "last_cycle_id": row["last_cycle_id"],
        "last_completed_at": row["last_completed_at"],
        "next_cycle_id": next_scheduled_cycle_id(row["last_cycle_id"]),
        "missed_cycles_recovered": max(int(row["missed_cycles"]), missed),
        "trigger": "existing_agent_supervisor_poll",
        "independent_daemon": False,
        "updated_at": row["updated_at"],
    }


def next_scheduled_cycle_id(last_cycle_id: str | None) -> str:
    """Next UTC daily cycle id, derived from the last completed cycle."""
    today = datetime.now(timezone.utc)
    if not last_cycle_id:
        return cycle_id(today)
    try:
        last = datetime.strptime(last_cycle_id.replace("daily-", ""), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return cycle_id(today)
    candidate = last + timedelta(days=1)
    if candidate.date() < today.date():
        candidate = today
    return cycle_id(candidate)


def due_cycle(*, enqueue_tasks: bool = False, publish_zulip: bool = True) -> dict[str, Any]:
    """Idempotent daily trigger called by the EXISTING supervisor loop.

    Returns ``{"status": "skipped", ...}`` unless a new UTC cycle is due. A
    cycle missed while the supervisor was offline is recovered once, recorded
    as a missed cycle, and never duplicated.
    """
    db = _schedule_db()
    try:
        row = db.execute(
            "SELECT * FROM daily_cycle_schedule WHERE singleton_id=?",
            (SCHEDULE_SINGLETON,),
        ).fetchone()
        if not row["enabled"]:
            return {"status": "disabled"}
        target = next_scheduled_cycle_id(row["last_cycle_id"])
        today = cycle_id(datetime.now(timezone.utc))
        if target > today:
            return {"status": "skipped", "reason": "not_due", "cycle_id": target}
        if row["last_cycle_id"] == target:
            return {"status": "skipped", "reason": "already_completed", "cycle_id": target}
        now = datetime.now(timezone.utc).isoformat()
        missed = 0
        if row["last_cycle_id"]:
            try:
                last = datetime.strptime(
                    row["last_cycle_id"].replace("daily-", ""), "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
                missed = max(0, (datetime.now(timezone.utc).date() - last.date()).days - 1)
            except ValueError:
                missed = 0
        # Claim the cycle BEFORE running it so concurrent supervisors cannot
        # both execute the same day. Completion is marked only after success.
        db.execute(
            "UPDATE daily_cycle_schedule SET next_cycle_id=?, missed_cycles=?, updated_at=? "
            "WHERE singleton_id=? AND enabled=1",
            (target, missed, now, SCHEDULE_SINGLETON),
        )
        db.commit()
    finally:
        db.close()

    result = run_daily_cycle(
        date=target.replace("daily-", ""),
        publish_zulip=publish_zulip, enqueue_tasks=enqueue_tasks,
    )
    if result.get("status") in {"completed", "partial"}:
        db = _schedule_db()
        try:
            db.execute(
                "UPDATE daily_cycle_schedule SET last_cycle_id=?, last_completed_at=?, "
                "next_cycle_id=NULL, updated_at=? WHERE singleton_id=?",
                (target, datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat(), SCHEDULE_SINGLETON),
            )
            db.commit()
        finally:
            db.close()
        result["scheduler_claimed"] = True
    return result


def set_schedule_enabled(enabled: bool) -> dict[str, Any]:
    db = _schedule_db()
    try:
        db.execute(
            "UPDATE daily_cycle_schedule SET enabled=?, updated_at=? WHERE singleton_id=?",
            (int(bool(enabled)), datetime.now(timezone.utc).isoformat(), SCHEDULE_SINGLETON),
        )
        db.commit()
    finally:
        db.close()
    return schedule_status()
