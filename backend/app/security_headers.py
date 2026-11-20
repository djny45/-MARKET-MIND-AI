"""Conservative security headers for API responses."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

_ASGIApp = Callable[[dict[str, Any], Callable[..., Awaitable[dict[str, Any]]], Callable[..., Awaitable[None]]], Awaitable[None]]


class SecurityHeadersMiddleware:
    """Add browser hardening headers without replacing proxy policy."""

    _BASE_HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
        (b"cross-origin-resource-policy", b"same-origin"),
    )

    def __init__(self, app: _ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                additions = [item for item in self._BASE_HEADERS if item[0] not in existing]
                if scope.get("path", "").startswith("/api/") and b"cache-control" not in existing:
                    additions.append((b"cache-control", b"no-store"))
                if scope.get("scheme") == "https" and b"strict-transport-security" not in existing:
                    additions.append((b"strict-transport-security", b"max-age=31536000"))
                message = {**message, "headers": headers + additions}
            await send(message)

        await self.app(scope, receive, send_with_headers)
