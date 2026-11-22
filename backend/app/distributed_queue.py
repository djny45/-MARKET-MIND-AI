"""Design of a distributed multi-host research queue (research-only).

The platform currently uses a single-host durable SQLite queue with a
supervisor. This module defines the interface a distributed implementation must
satisfy: job lifecycle with leases, idempotency, at-least-once delivery,
dead-letter handling, retry policy, observability and capacity gating.

Nothing here connects to an external broker. It is design + validation code.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

MAX_CLAIM_LEASE_SECONDS = 86_400
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 30


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEADLETTER = "deadletter"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_seconds: int = DEFAULT_BACKOFF_SECONDS

    def validate(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")


@dataclass(frozen=True)
class Job:
    id: str
    idempotency_key: str
    queue_key: str
    body: dict
    worker_id: str
    status: JobStatus
    attempts: int
    created_at: float
    lease_expires_at: float | None = None
    deadline_at: float | None = None
    result: dict | None = None
    last_error: str = ""
    parent_job_id: str | None = None
    replay_of: str | None = None


class MultiHostQueue(Protocol):
    """Contract a distributed research queue must implement."""

    cluster_id: str
    job_store_uri: str

    def validate_config(self) -> None:
        raise NotImplementedError

    def enqueue(
        self,
        queue_key: str,
        body: dict,
        idempotency_key: str,
        parent_job_id: str | None = None,
    ) -> Job:
        raise NotImplementedError

    def claim(self, worker_id: str, lease_seconds: int) -> Job | None:
        raise NotImplementedError

    def complete(self, job: Job, result: dict | None = None) -> Job:
        raise NotImplementedError

    def fail(self, job: Job, error: str) -> Job:
        raise NotImplementedError

    def cancel(self, job: Job, reason: str) -> Job:
        raise NotImplementedError

    def stats(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class QueueCapabilities:
    single_host_supported: bool = True
    multi_host_supported: bool = False
    at_least_once: bool = True
    exactly_once: bool = False
    idempotency: bool = True
    deadletter: bool = True
    durable_store: str = "sqlite"
    replication_needed_for_multi_host: str = "external: transactional store (e.g. Postgres with advisory locks)"


def lease_deadline(lease_seconds: int) -> float:
    if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool):
        raise ValueError("lease_seconds must be an int")
    if not 1 <= lease_seconds <= MAX_CLAIM_LEASE_SECONDS:
        raise ValueError("lease_seconds out of range")
    return time.time() + lease_seconds


def idempotency_key_required(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("idempotency_key is required")
    return key.strip()


def capabilities() -> QueueCapabilities:
    return QueueCapabilities()
