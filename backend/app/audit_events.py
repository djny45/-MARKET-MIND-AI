"""Append-only, in-memory security audit-event aggregation.

Events carry an event type, actor, resource, action, outcome and timestamp.
The aggregator is thread-safe, bounded, and redacts secret-looking fields so
that credentials never appear in audit output. It is a research-platform
accounting record, not a tamper-proof log or a brokerage/trading audit trail.
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

EVENT_TYPES = frozenset(
    {
        "authentication",
        "authorization",
        "csrf",
        "session",
        "rate_limit",
        "configuration",
        "resource",
        "security",
        "audit_access",
        "startup",
    }
)
OUTCOMES = frozenset({"success", "denied", "failure", "info", "throttled"})
REDACTED = "[REDACTED]"
_SECRET_KEY = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|cookie|csrf|credential|private[_-]?key)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
# Session tokens are 43-char base64url values; JWT-shaped values are also
# credentials. Match whole tokens so legitimate 64-char research hashes stay
# visible in audit evidence.
_HIGH_ENTROPY_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9_-]{43}"
    r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"
    r"(?![A-Za-z0-9_-])"
)
_MAX_TEXT = 300


def _redact_text(text: str) -> str:
    """Remove bearer credentials and token-shaped values from free text."""
    text = _BEARER.sub(f"Bearer {REDACTED}", text)
    return _HIGH_ENTROPY_TOKEN.sub(REDACTED, text)


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact secret-looking keys and inline bearer credentials."""
    if _depth > 8:
        return REDACTED
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEY.search(key_text):
                result[key_text] = REDACTED
            else:
                result[key_text] = redact(item, _depth=_depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [redact(item, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        return _redact_text(value)[:_MAX_TEXT]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return REDACTED


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    actor: str
    actor_role: str
    resource: str
    action: str
    outcome: str
    timestamp: str
    metadata: dict[str, Any]


class AuditEventAggregator:
    """Bounded, thread-safe append-only aggregator for security events."""

    def __init__(self, capacity: int = 2000) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._events: deque[AuditEvent] = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._sequence = 0

    @staticmethod
    def _text(value: Any, label: str) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            text = value
        elif isinstance(value, Mapping):
            text = str({k: v for k, v in value.items() if not _SECRET_KEY.search(str(k))})
        else:
            text = str(value)
        text = _redact_text(text)
        if len(text) > _MAX_TEXT:
            text = text[:_MAX_TEXT] + "..."
        del label
        return text

    def record(
        self,
        event_type: str,
        actor: Any,
        resource: Any,
        action: str,
        outcome: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        timestamp: float | None = None,
    ) -> AuditEvent:
        """Append one redacted event and return its immutable snapshot."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {event_type}")
        if outcome not in OUTCOMES:
            raise ValueError(f"unsupported outcome: {outcome}")
        actor_name, actor_role = self._actor_fields(actor)
        stamp = time.time() if timestamp is None else float(timestamp)
        created = datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()
        with self._lock:
            self._sequence += 1
            event_id = f"evt-{self._sequence:08d}"
            event = AuditEvent(
                event_id=event_id,
                event_type=event_type,
                actor=actor_name,
                actor_role=actor_role,
                resource=self._text(resource, "resource"),
                action=self._text(action, "action"),
                outcome=outcome,
                timestamp=created,
                metadata=redact(dict(metadata or {})),
            )
            # Copy-on-write is unnecessary: events are frozen and never mutated.
            self._events.append(event)
            return event

    @staticmethod
    def _actor_fields(actor: Any) -> tuple[str, str]:
        if actor is None:
            return "anonymous", "unauthenticated"
        if isinstance(actor, Mapping):
            username = actor.get("username", "anonymous")
            role = actor.get("role", "unknown")
            return str(username)[:_MAX_TEXT], str(role)[:40]
        return str(actor)[:_MAX_TEXT], "unknown"

    def recent(
        self,
        limit: int = 100,
        *,
        event_type: str | None = None,
        actor: str | None = None,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return newest-first event dictionaries with optional exact filters."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if event_type is not None and event_type not in EVENT_TYPES:
            raise ValueError("unsupported event_type filter")
        if outcome is not None and outcome not in OUTCOMES:
            raise ValueError("unsupported outcome filter")
        with self._lock:
            snapshot = list(self._events)
        matches = []
        for event in reversed(snapshot):
            if event_type is not None and event.event_type != event_type:
                continue
            if actor is not None and event.actor != actor:
                continue
            if outcome is not None and event.outcome != outcome:
                continue
            matches.append(asdict(event))
            if len(matches) >= limit:
                break
        return matches

    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def clear(self) -> None:
        """Testing/startup helper: intentionally unavailable through the API."""
        with self._lock:
            self._events.clear()
            self._sequence = 0


audit_log = AuditEventAggregator()


def record_authorization_decision(
    aggregator: AuditEventAggregator,
    actor: Any,
    *,
    resource: str,
    action: str,
    decision: Any,
) -> AuditEvent:
    """Convenience wrapper used by authorization dependencies and middleware."""
    allowed = bool(getattr(decision, "allowed", False))
    reason = str(getattr(decision, "reason", "unknown"))
    return aggregator.record(
        "authorization",
        actor,
        resource,
        action,
        "success" if allowed else "denied",
        metadata={"reason": reason, "required_role": getattr(decision, "required_role", None)},
    )


__all__ = [
    "EVENT_TYPES",
    "OUTCOMES",
    "REDACTED",
    "AuditEvent",
    "AuditEventAggregator",
    "audit_log",
    "redact",
    "record_authorization_decision",
]
