"""Deterministic cross-market research message bus.

Agents are software research modules, not language models or trading bots.
Messages are persisted as evidence-linked research notes and shared across the
India, US, crypto and forex domains. No live feeds or execution are provided.
"""
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

MARKET_GROUPS = ("india", "us", "crypto", "forex")
_ID = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")
_TOPICS = {"macro", "correlation", "volatility", "liquidity", "breadth",
           "event", "data_quality", "research_note", "regime"}


def _connect():
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_messages (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            market_group TEXT NOT NULL,
            topic TEXT NOT NULL,
            instrument_id TEXT,
            published_at TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            quality_status TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_messages_market_time ON agent_messages(market_group, published_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_messages_topic_time ON agent_messages(topic, published_at)")
    return db


def publish_message(message):
    if not isinstance(message, dict):
        raise ValueError("message must be an object")
    agent_id = message.get("agent_id")
    if not isinstance(agent_id, str) or not _ID.fullmatch(agent_id):
        raise ValueError("agent_id must contain 1 to 96 permitted characters")
    market_group = message.get("market_group")
    if market_group not in MARKET_GROUPS:
        raise ValueError("market_group must be one of india, us, crypto, forex")
    topic = message.get("topic")
    if topic not in _TOPICS:
        raise ValueError("topic is unsupported")
    instrument_id = message.get("instrument_id")
    if instrument_id is not None and (not isinstance(instrument_id, str) or not _ID.fullmatch(instrument_id)):
        raise ValueError("instrument_id must contain 1 to 96 permitted characters")
    payload = message.get("payload")
    if not isinstance(payload, dict) or len(json.dumps(payload, default=str)) > 16000:
        raise ValueError("payload must be an object no larger than 16000 characters")
    refs = message.get("source_refs", [])
    if not isinstance(refs, list) or len(refs) > 20 or any(not isinstance(x, str) or len(x) > 300 for x in refs):
        raise ValueError("source_refs must be an array of at most 20 strings")
    quality = message.get("quality_status", "unverified")
    if quality not in {"verified_by_importer", "partial", "unverified", "synthetic"}:
        raise ValueError("quality_status is unsupported")
    message_id = str(uuid.uuid4())
    published_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute(
            "INSERT INTO agent_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (message_id, agent_id, market_group, topic, instrument_id, published_at,
             json.dumps(refs), quality, json.dumps(payload, sort_keys=True, allow_nan=False)),
        )
    return {"message_id": message_id, "agent_id": agent_id, "market_group": market_group,
            "topic": topic, "published_at": published_at, "quality_status": quality,
            "shared_network": "four_market_mesh",
            "note": "Published to the shared research bus; this is not an AI-generated conclusion or trading instruction."}


def read_messages(market_group=None, topic=None, limit=100):
    if market_group is not None and market_group not in MARKET_GROUPS:
        raise ValueError("market_group must be one of india, us, crypto, forex")
    if topic is not None and topic not in _TOPICS:
        raise ValueError("topic is unsupported")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    clauses, params = [], []
    if market_group is not None:
        clauses.append("market_group=?")
        params.append(market_group)
    if topic is not None:
        clauses.append("topic=?")
        params.append(topic)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM agent_messages" + where + " ORDER BY published_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM agent_messages" + where, params).fetchone()[0]
    messages = []
    for row in rows:
        item = dict(row)
        item["source_refs"] = json.loads(item.pop("source_refs_json"))
        item["payload"] = json.loads(item.pop("payload_json"))
        messages.append(item)
    peer_groups = sorted({m["market_group"] for m in messages})
    return {"count": len(messages), "total_matching": total, "messages": messages,
            "peer_market_groups_in_sample": peer_groups,
            "cross_market_context": len(peer_groups) > 1,
            "market_groups": list(MARKET_GROUPS),
            "note": "Messages are caller-supplied research records. Shared context does not imply synchronized data, causal relationships, completeness or validated conclusions."}


def network_topology():
    return {"network": "four_market_mesh", "mode": "deterministic_message_bus",
            "market_groups": [{"id": group, "can_publish": True, "can_read_shared_messages": True}
                              for group in MARKET_GROUPS],
            "connections": [{"from": source, "to": target}
                            for source in MARKET_GROUPS for target in MARKET_GROUPS if source != target],
            "agent_runtime": "analytical modules only; no LLM inference",
            "data_mode": "historical, manually imported or synthetic fixtures only",
            "execution": {"paper_trading": False, "broker_execution": False},
            "note": "Logical message sharing is implemented; no external agents or live market feeds are connected."}
