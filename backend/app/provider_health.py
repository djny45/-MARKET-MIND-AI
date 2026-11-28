"""Provider freshness and health reporting for research-only market data.

This module aggregates the status metadata already carried by
``MarketDataBatch`` batches (live / delayed / historical / synthetic) together
with local success/failure observations and the licensing gate. It performs
NO external calls and grants no provider access: activating a live or delayed
provider still requires an explicit license review and operator approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from app.data_licensing_gate import DataLicensingGate
from app.market_data import DataStatus

# Maximum acceptable age, in seconds, for a batch of each status. These are
# descriptive thresholds for the research UI, not trading SLAs.
#
# UNAVAILABLE is deliberately absent: it is not an observation, so there is no
# age to test. ``freshness`` reports "unknown" for it and ``health`` degrades,
# which is the honest outcome for a provider that has nothing to serve.
FRESHNESS_THRESHOLDS: dict[DataStatus, int] = {
    DataStatus.LIVE: 60,
    DataStatus.DELAYED: 15 * 60,
    DataStatus.HISTORICAL: 7 * 24 * 3600,
    DataStatus.SYNTHETIC: 3600,
}

HEALTHY = "healthy"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"

FRESH = "fresh"
STALE = "stale"
UNKNOWN = "unknown"


@dataclass
class ProviderObservation:
    name: str
    status: DataStatus | None = None
    source: str | None = None
    retrieved_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str = ""
    consecutive_failures: int = 0
    observations: int = 0
    warnings: list[str] = field(default_factory=list)


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _status_of(value: Any) -> DataStatus | None:
    if isinstance(value, DataStatus):
        return value
    if isinstance(value, str):
        try:
            return DataStatus(value.strip().lower())
        except ValueError:
            return None
    return None


class ProviderHealthRegistry:
    """Thread-safe-by-convention in-memory registry of provider observations."""

    def __init__(self, licensing_gate: DataLicensingGate | None = None):
        self.licensing_gate = licensing_gate or DataLicensingGate()
        self._providers: dict[str, ProviderObservation] = {}

    def register(self, name: str, status: DataStatus | str | None = None) -> ProviderObservation:
        key = str(name).strip()
        if not key:
            raise ValueError("provider name is required")
        observation = self._providers.setdefault(
            key, ProviderObservation(name=key)
        )
        if status is not None:
            observation.status = _status_of(status)
        return observation

    def record_success(self, batch: Any) -> ProviderObservation:
        """Record a successful batch using its own source/status metadata."""
        source = getattr(batch, "source", None)
        if not source:
            raise ValueError("batch must declare a source")
        observation = self.register(str(source))
        observation.status = _status_of(getattr(batch, "status", None))
        observation.retrieved_at = _as_aware(getattr(batch, "retrieved_at", None))
        observation.last_success_at = observation.retrieved_at or _aware_now()
        observation.consecutive_failures = 0
        observation.observations += 1
        observation.warnings = [
            str(item) for item in (getattr(batch, "warnings", None) or [])
        ]
        return observation

    def record_failure(self, provider: str, error: str) -> ProviderObservation:
        observation = self.register(provider)
        observation.last_error = str(error)[:500]
        observation.consecutive_failures += 1
        observation.observations += 1
        return observation

    def freshness(
        self,
        observation: ProviderObservation,
        now: datetime | None = None,
    ) -> tuple[str, int | None]:
        reference = _as_aware(now) or _aware_now()
        timestamp = _as_aware(observation.retrieved_at or observation.last_success_at)
        if timestamp is None:
            return UNKNOWN, None
        age = max(0, int((reference - timestamp).total_seconds()))
        threshold = FRESHNESS_THRESHOLDS.get(observation.status)
        if threshold is None:
            return UNKNOWN, age
        return (FRESH if age <= threshold else STALE), age

    def health(self, observation: ProviderObservation, now: datetime | None = None) -> str:
        if observation.consecutive_failures >= 3:
            return UNAVAILABLE
        if observation.consecutive_failures > 0:
            return DEGRADED
        freshness, age = self.freshness(observation, now)
        if freshness == UNKNOWN or freshness == STALE:
            return DEGRADED
        if age is not None and observation.status == DataStatus.SYNTHETIC:
            return DEGRADED  # synthetic data is never a healthy live feed
        return HEALTHY

    def report(self, now: datetime | None = None) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        for name in sorted(self._providers):
            observation = self._providers[name]
            freshness, age = self.freshness(observation, now)
            health = self.health(observation, now)
            licensing: dict[str, Any] | None = None
            try:
                licensing = self.licensing_gate.validate(name)
            except ValueError:
                licensing = None  # local/synthetic sources have no provider policy
            providers.append({
                "name": name,
                "status": observation.status.value if observation.status else None,
                "source": observation.source or name,
                "freshness": freshness,
                "age_seconds": age,
                "health": health,
                "consecutive_failures": observation.consecutive_failures,
                "observations": observation.observations,
                "last_error": observation.last_error or None,
                "warnings": list(observation.warnings),
                "licensing": {
                    "status": licensing["status"],
                    "authorized": licensing["authorized"],
                } if licensing else None,
            })
        return {
            "providers": providers,
            "research_only": True,
            "broker_execution": False,
            "live_provider_activation": "requires_license_review_and_operator_approval",
            "note": (
                "Statuses describe local observations only. Synthetic fixtures "
                "are not live, delayed, or historical market prices."
            ),
        }


_registry: ProviderHealthRegistry | None = None


def get_provider_health_registry() -> ProviderHealthRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderHealthRegistry()
    return _registry
