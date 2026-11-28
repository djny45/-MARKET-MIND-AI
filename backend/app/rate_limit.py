"""Optional in-process request rate limiting for the research API.

Disabled by default. Set API_RATE_LIMIT_PER_MINUTE to a positive integer to
allow at most that many requests per client IP per 60-second window. This is a
basic single-process abuse guard; production deployments should also enforce
limits at the ingress/proxy layer.
"""
from __future__ import annotations

import os
import time
from typing import Any

from starlette.responses import JSONResponse

from .distributed_rate_limit import client_key
from .env_validation import trusted_proxy_settings
from .audit_events import audit_log

EXEMPT_PATHS = frozenset({"/api/health", "/api/ready"})
MAX_TRACKED_CLIENTS = 4_096


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self._hits: dict[str, list[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    @staticmethod
    def _limit() -> int:
        try:
            value = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "0").strip())
        except (TypeError, ValueError):
            return 0
        return max(0, value)

    @staticmethod
    def _client(scope: dict[str, Any]) -> str:
        proxy = trusted_proxy_settings()
        return client_key(
            scope, trusted_proxies=proxy["count"], header=proxy["header"]
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._limit()
        path = scope.get("path", "")
        if (
            limit <= 0
            or scope.get("method", "GET").upper() == "OPTIONS"
            or path in EXEMPT_PATHS
        ):
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        key = self._client(scope)
        hits = [stamp for stamp in self._hits.get(key, []) if now - stamp < 60]
        if len(hits) >= limit:
            retry_after = max(1, int(60 - (now - hits[0])))
            audit_log.record("rate_limit", None, path, "request", "throttled",
                             metadata={"backend": "in-process", "retry_after_seconds": retry_after})
            response = JSONResponse(
                {"detail": "Rate limit exceeded."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        if key not in self._hits and len(self._hits) >= MAX_TRACKED_CLIENTS:
            expired = next(
                (name for name, values in self._hits.items()
                 if not values or all(now - stamp >= 60 for stamp in values)),
                None,
            )
            if expired is None:
                # All tracked buckets are active: fail closed instead of
                # evicting a client that is still inside its window.
                audit_log.record("rate_limit", None, path, "request", "throttled",
                                 metadata={"backend": "in-process", "reason": "client_limit_full"})
                response = JSONResponse(
                    {"detail": "Rate limit exceeded."}, status_code=429,
                    headers={"Retry-After": "60"},
                )
                await response(scope, receive, send)
                return
            self._hits.pop(expired)
        hits.append(now)
        self._hits[key] = hits
        await self.app(scope, receive, send)
