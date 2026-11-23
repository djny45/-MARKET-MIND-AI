"""Redis-backed request rate limiting with a safe in-process fallback.

When ``REDIS_URL`` is configured and a Redis client is available, checks use a
single atomic Lua script (INCR + first-hit EXPIRE). Any connection/runtime
failure degrades to a bounded in-process sliding-window limiter instead of
failing open. Health and readiness probes are always exempt.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from starlette.responses import JSONResponse

EXEMPT_PATHS = frozenset({"/api/health", "/api/ready"})
MAX_TRACKED_CLIENTS = 4_096
DEFAULT_WINDOW_SECONDS = 60

# One round trip; the counter and its first expiration are applied atomically.
INCREMENT_AND_EXPIRE_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    backend: str
    remaining: int
    retry_after: int


class _LocalWindow:
    """Bounded sliding-window limiter used as the fallback backend."""

    def __init__(self, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> None:
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def check(self, key: str, limit: int, now: float) -> RateLimitResult:
        with self._lock:
            hits = [stamp for stamp in self._hits.get(key, ()) if now - stamp < self._window]
            if len(hits) >= limit:
                retry = max(1, int(self._window - (now - hits[0])))
                self._hits[key] = hits
                return RateLimitResult(False, "in-process", 0, retry)
            hits.append(now)
            if len(self._hits) >= MAX_TRACKED_CLIENTS and key not in self._hits:
                self._hits.clear()
            self._hits[key] = hits
            return RateLimitResult(True, "in-process", max(0, limit - len(hits)), 0)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class DistributedRateLimiter:
    """Atomic Redis limiter with automatic, safe local degradation."""

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        limit: int = 0,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        client: Any | None = None,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, int)
            or window_seconds <= 0
        ):
            raise ValueError("window_seconds must be a positive integer")
        self.limit = limit
        self.window_seconds = window_seconds
        self._local = _LocalWindow(window_seconds)
        self._client: Any | None = None
        self._redis_disabled = False
        self._redis_retry_after = 0.0
        self._redis_cooldown_seconds = 5.0
        self._now = time.monotonic

        if client is not None:
            self._client = client
            return
        if redis_url and isinstance(redis_url, str) and redis_url.strip():
            self._client = self._connect(redis_url.strip())

    @staticmethod
    def _connect(redis_url: str) -> Any | None:
        try:
            import redis  # type: ignore
        except ImportError:
            return None
        try:
            client = redis.from_url(
                redis_url,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
                decode_responses=True,
            )
            client.ping()
            return client
        except Exception:
            # Never allow a misconfigured/unavailable Redis instance to block
            # startup or to fail open; the local backend takes over.
            return None

    @property
    def backend(self) -> str:
        return "redis" if self._client is not None and not self._redis_disabled else "in-process"

    def check(self, key: str) -> RateLimitResult:
        if self.limit <= 0:
            return RateLimitResult(True, self.backend, 0, 0)
        if not isinstance(key, str) or not key:
            key = "unknown"

        redis_key = f"mm:rl:{self.window_seconds}:{key}"
        now = self._now()
        if self._client is not None and (
            not self._redis_disabled or now >= self._redis_retry_after
        ):
            try:
                current = int(
                    self._client.eval(INCREMENT_AND_EXPIRE_LUA, 1, redis_key, self.window_seconds)
                )
            except Exception:
                # Degrade to the local limiter, but retry Redis after a short
                # cooldown instead of permanently abandoning a recovered host.
                self._redis_disabled = True
                self._redis_retry_after = now + self._redis_cooldown_seconds
            else:
                self._redis_disabled = False
                self._redis_retry_after = 0.0
                if current > self.limit:
                    return RateLimitResult(False, "redis", 0, self.window_seconds)
                return RateLimitResult(True, "redis", self.limit - current, 0)
        return self._local.check(key, self.limit, now)

    def reset(self) -> None:
        """Clear local state (and, when safe, the known Redis keys)."""
        self._local.reset()
        self._redis_disabled = False
        self._redis_retry_after = 0.0


def client_key(
    scope: Mapping[str, Any], *, trusted_proxies: int = 0, header: str = "x-forwarded-for"
) -> str:
    """Derive a rate-limit key, honouring only explicitly trusted proxies."""
    client = scope.get("client")
    base = str(client[0]) if client and isinstance(client, (tuple, list)) and client else "unknown"
    if trusted_proxies <= 0:
        return base
    header_bytes = (header or "x-forwarded-for").strip().lower().encode("ascii")
    forwarded = ""
    for name, value in scope.get("headers", []):
        if name.lower() == header_bytes:
            forwarded = value.decode("latin-1")
            break
    if forwarded:
        candidates = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(candidates) >= trusted_proxies:
            return candidates[-trusted_proxies]
    return base


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


class DistributedRateLimitMiddleware:
    """ASGI middleware wrapping ``DistributedRateLimiter``.

    It is a no-op unless ``REDIS_URL`` and a positive
    ``API_RATE_LIMIT_PER_MINUTE`` are both configured, so existing in-process
    rate limiting and the 987+ test suite remain unchanged in local mode.
    """

    def __init__(self, app: Any, limiter: DistributedRateLimiter | None = None) -> None:
        self.app = app
        self._limiter = limiter
        self._injected = limiter is not None
        self._signature: tuple[str, int, int] | None = None

    def _configured_limiter(self) -> DistributedRateLimiter | None:
        redis_url = os.getenv("REDIS_URL", "").strip()
        limit = _env_int("API_RATE_LIMIT_PER_MINUTE")
        if self._injected:
            return self._limiter if limit > 0 else None
        if not redis_url or limit <= 0:
            return None
        from .env_validation import trusted_proxy_settings

        proxy = trusted_proxy_settings()
        signature = (redis_url, limit, proxy["count"], proxy["header"])
        if self._signature != signature or self._limiter is None:
            self._limiter = DistributedRateLimiter(redis_url, limit=limit)
            self._signature = signature
        return self._limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if (
            scope.get("method", "GET").upper() == "OPTIONS"
            or path in EXEMPT_PATHS
        ):
            await self.app(scope, receive, send)
            return
        limiter = self._configured_limiter()
        if limiter is None:
            await self.app(scope, receive, send)
            return

        from .env_validation import trusted_proxy_settings

        proxy = trusted_proxy_settings()
        result = limiter.check(
            client_key(scope, trusted_proxies=proxy["count"], header=proxy["header"])
        )
        if not result.allowed:
            response = JSONResponse(
                {
                    "detail": "Rate limit exceeded.",
                    "backend": result.backend,
                },
                status_code=429,
                headers={"Retry-After": str(result.retry_after)},
            )
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})["rate_limit_backend"] = result.backend
        await self.app(scope, receive, send)


__all__ = [
    "DEFAULT_WINDOW_SECONDS",
    "EXEMPT_PATHS",
    "INCREMENT_AND_EXPIRE_LUA",
    "DistributedRateLimiter",
    "DistributedRateLimitMiddleware",
    "RateLimitResult",
    "client_key",
]
