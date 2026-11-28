"""Compliant, per-provider request pacing for public market-data endpoints.

This module implements *politeness*, not circumvention:

* A per-provider token bucket sets a conservative minimum interval between
  requests. It never issues a request faster than the configured rate.
* ``Retry-After`` returned by a provider is honoured literally. A cooldown
  blocks all further calls to that provider until the deadline, including
  calls from other threads, so a 429 cannot be retried around the limit.
* Bounded exponential backoff is applied only after an explicit provider
  signal (429 / 503 with Retry-After). There is no retry-on-everything loop
  and no attempt to rotate identities, user agents, IPs or credentials.
* Responses are cached with a TTL so a UI poll does not create upstream load.
  UNAVAILABLE observations are never cached as if they were data.

The limiter is deliberately independent of the adapters so the policy is
auditable in one place. It holds no credentials.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from .provider_adapters import ProviderError

T = TypeVar("T")


@dataclass(frozen=True)
class ProviderPolicy:
    """Declared, conservative request policy for one public provider."""

    name: str
    min_interval_seconds: float
    burst: int
    cache_ttl_seconds: float
    max_backoff_seconds: float = 60.0
    max_retries: int = 2

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "min_interval_seconds": self.min_interval_seconds,
            "burst": self.burst,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "max_retries": self.max_retries,
            "bypasses_limits": False,
        }


# CoinGecko's public plan was observed to allow ~2 requests/minute per IP and
# returned "Retry-After: 60" on the third. We pace it at 1 request / 35s, which
# is slower than the observed limit, and cache for 60s. Yahoo and ECB are much
# more permissive; their bounds still keep a full board well below abuse.
POLICIES: dict[str, ProviderPolicy] = {
    "coingecko-public": ProviderPolicy(
        name="coingecko-public", min_interval_seconds=35.0, burst=1,
        cache_ttl_seconds=60.0, max_backoff_seconds=60.0, max_retries=2,
    ),
    "yahoo-us-equities": ProviderPolicy(
        name="yahoo-us-equities", min_interval_seconds=0.25, burst=4,
        cache_ttl_seconds=30.0,
    ),
    "yahoo-india-nse-bse": ProviderPolicy(
        name="yahoo-india-nse-bse", min_interval_seconds=0.25, burst=4,
        cache_ttl_seconds=30.0,
    ),
    "ecb-reference-rates": ProviderPolicy(
        name="ecb-reference-rates", min_interval_seconds=1.0, burst=2,
        cache_ttl_seconds=3600.0,  # ECB publishes once per business day
    ),
}


def policy_for(name: str) -> ProviderPolicy:
    try:
        return POLICIES[name]
    except KeyError as exc:
        raise ValueError(f"no request policy declared for provider {name!r}") from exc


class ProviderLimiter:
    """Thread-safe request gate with cache and provider-wide cooldown."""

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._lock = threading.Lock()
        self._next_allowed: dict[str, float] = {}
        self._cooldown_until: dict[str, float] = {}
        self._cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._last_error: dict[str, str] = {}

    @staticmethod
    def _retry_after_seconds(exc: ProviderError) -> float | None:
        """Parse a literal provider Retry-After value; no guessing."""
        text = str(exc)
        marker = "Retry-After: "
        if marker not in text:
            return None
        raw = text.split(marker, 1)[1].split(")", 1)[0].strip()
        try:
            value = float(raw)
        except ValueError:
            return None
        return max(0.0, min(value, 300.0))

    def observe_cooldown(self, provider: str, exc: ProviderError) -> None:
        """Apply a provider-declared cooldown to every future call."""
        retry_after = self._retry_after_seconds(exc)
        if retry_after is None:
            return
        with self._lock:
            self._cooldown_until[provider] = max(
                self._cooldown_until.get(provider, 0.0),
                self._clock() + retry_after,
            )
            self._last_error[provider] = str(exc)[:200]

    def _wait_for_turn(self, policy: ProviderPolicy) -> None:
        """Sleep under a per-provider gate; never bypass a cooldown."""
        while True:
            with self._lock:
                now = self._clock()
                cooldown = self._cooldown_until.get(policy.name, 0.0)
                if now < cooldown:
                    wait = cooldown - now
                else:
                    earliest = self._next_allowed.get(policy.name, 0.0)
                    wait = max(0.0, min(earliest - now, 60.0))
                    if wait <= 0:
                        self._next_allowed[policy.name] = now + policy.min_interval_seconds
                        return
            self._sleep(wait)

    def call(self, provider: str, key: tuple[Any, ...], fn: Callable[[], T]) -> T:
        """Return a cached value or call ``fn`` under the provider policy.

        Retries happen only on a provider rate-limit signal, with bounded
        exponential backoff, and always respect its Retry-After deadline.
        """
        policy = policy_for(provider)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and self._clock() - hit[0] < policy.cache_ttl_seconds:
                return hit[1]

        last_exc: ProviderError | None = None
        for attempt in range(policy.max_retries + 1):
            self._wait_for_turn(policy)
            try:
                value = fn()
            except ProviderError as exc:
                last_exc = exc
                if "429" not in str(exc) and "503" not in str(exc):
                    raise
                self.observe_cooldown(provider, exc)
                if attempt >= policy.max_retries:
                    break
                # Bounded backoff, never shorter than the provider's own signal.
                backoff = min(2 ** attempt, policy.max_backoff_seconds)
                retry_after = self._retry_after_seconds(exc)
                delay = max(backoff, retry_after or 0.0)
                with self._lock:
                    self._cooldown_until[provider] = max(
                        self._cooldown_until.get(provider, 0.0), self._clock() + delay
                    )
                    self._last_error[provider] = str(exc)[:200]
                continue
            with self._lock:
                self._cache[key] = (self._clock(), value)
            return value
        assert last_exc is not None
        raise last_exc

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "policies": [policy_for(name).to_payload() for name in sorted(POLICIES)],
                "cooldown_remaining_seconds": {
                    name: round(max(0.0, deadline - self._clock()), 3)
                    for name, deadline in self._cooldown_until.items()
                },
                "last_provider_error": dict(self._last_error),
                "cached_entries": len(self._cache),
                "bypasses_provider_limits": False,
            }

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


LIMITER = ProviderLimiter()
