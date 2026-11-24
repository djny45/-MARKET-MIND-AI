"""Opt-in per-user session enforcement and browser-hardening middleware."""
from __future__ import annotations

import os
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlparse

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from .audit_events import audit_log, redact, record_authorization_decision
from .authorization import (
    authorize,
    bind_actor,
    hmac_compare,
    required_role_for_path,
    reset_actor,
    safe_actor,
)
from .env_validation import (
    allowed_origins,
    cookie_settings,
    origin_required,
    trusted_proxy_settings,
)
from .user_auth import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    csrf_matches,
    enabled,
    get_user_session,
)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Environment validation is intentionally NOT exempt: it is a sensitive,
# role-protected endpoint. Health/readiness/login remain reachable.
EXEMPT_PATHS = frozenset({"/api/health", "/api/ready", "/api/auth/login"})
_FORWARDED_HEADERS = frozenset(
    {b"x-forwarded-for", b"x-real-ip", b"x-forwarded-proto", b"x-forwarded-host"}
)


def _cookies(scope: dict[str, Any]) -> SimpleCookie:
    jar: SimpleCookie = SimpleCookie()
    for name, value in scope.get("headers", []):
        if name.lower() == b"cookie":
            try:
                jar.load(value.decode("latin-1"))
            except Exception:
                pass
    return jar


def _header_values(scope: dict[str, Any], name: bytes) -> list[str]:
    return [
        value.decode("latin-1")
        for key, value in scope.get("headers", [])
        if key.lower() == name
    ]


def set_session_cookies(response: Any, session_token: str, csrf_token: str) -> None:
    """Apply the configured SameSite/Secure/HttpOnly cookie attributes."""
    settings = cookie_settings()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=settings["httponly"],
        samesite=settings["samesite"],
        secure=settings["secure"],
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,  # the browser client must echo this in a header
        samesite=settings["samesite"],
        secure=settings["secure"],
        path="/",
    )


def clear_session_cookies(response: Any) -> None:
    settings = cookie_settings()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite=settings["samesite"], secure=settings["secure"])
    response.delete_cookie(CSRF_COOKIE, path="/", samesite=settings["samesite"], secure=settings["secure"])


def _origin_allowed(scope: dict[str, Any]) -> bool:
    origins = [origin.lower() for origin in allowed_origins()]
    if not origins:
        return False
    candidates = _header_values(scope, b"origin") + _header_values(scope, b"referer")
    if not candidates:
        return False
    for candidate in candidates:
        try:
            parsed = urlparse(candidate.strip())
        except ValueError:
            # Origin/Referer are attacker-controlled. A malformed value must
            # not turn an authorization check into a 500.
            continue
        origin = f"{parsed.scheme}://{parsed.netloc}".lower()
        if parsed.scheme and parsed.netloc and any(hmac_compare(origin, allowed) for allowed in origins):
            return True
    return False


def _strip_untrusted_forwarded_headers(scope: dict[str, Any]) -> None:
    """Ignore proxy hints unless a trusted proxy count is configured."""
    if trusted_proxy_settings()["count"] > 0:
        return
    headers = scope.get("headers")
    if headers is None:
        return
    scope["headers"] = [
        (name, value) for name, value in headers if name.lower() not in _FORWARDED_HEADERS
    ]


class UserSessionAuthMiddleware:
    """Validate session cookies, bind CSRF tokens, and enforce role policy.

    No-ops unless MARKET_MIND_USER_AUTH is enabled, so local research and the
    existing test suite keep working without credentials.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        _strip_untrusted_forwarded_headers(scope)
        if not enabled() and os.getenv("API_AUTH_REQUIRED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }:
            # Shared deployment bearer: authenticated but never administrative.
            # Per-user roles require MARKET_MIND_USER_AUTH; a bearer holder is
            # explicitly downgraded to viewer for sensitive-route policy checks.
            path = scope.get("path", "")
            policy = required_role_for_path(path, scope.get("method", "GET").upper())
            if policy is not None:
                decision = authorize(
                    {"username": "api-client", "role": "viewer"}, policy[0]
                )
                if not decision.allowed:
                    audit_log.record("authorization", None, path, "bearer_policy", "denied")
                    response = JSONResponse(
                        {"detail": f"Authorization denied: {decision.reason}"}, status_code=403
                    )
                    await response(scope, receive, send)
                    return
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        if not enabled() or not path.startswith("/api/") or method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if path == "/api/auth/login" and method == "POST":
            # Login has no session or CSRF token yet, so a token check is
            # impossible here. A browser-forced login is still prevented by
            # rejecting an explicitly supplied cross-site Origin, while API
            # clients that send no Origin keep working. The route separately
            # requires application/json, blocking text/plain form posts.
            if _header_values(scope, b"origin") and not _origin_allowed(scope):
                audit_log.record("csrf", None, path, "login_origin", "denied")
                response = JSONResponse(
                    {"detail": "Request origin is not allowed."}, status_code=403
                )
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return
        if path in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        jar = _cookies(scope)
        token = jar[SESSION_COOKIE].value if SESSION_COOKIE in jar else ""
        session = get_user_session(token)
        if session is None:
            audit_log.record("authentication", None, scope.get("path", ""), "session_check", "denied")
            response = JSONResponse(
                {"detail": "Valid user session required."},
                status_code=401,
                headers={"WWW-Authenticate": "Session"},
            )
            await response(scope, receive, send)
            return

        actor = {"username": session["username"], "role": session["role"]}
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()

        policy = required_role_for_path(path, method)
        if policy is not None:
            decision = authorize(actor, policy[0])
            if not decision.allowed:
                record_authorization_decision(
                    audit_log, actor, resource=policy[1], action=path, decision=decision
                )
                response = JSONResponse(
                    {"detail": f"Authorization denied: {decision.reason}"}, status_code=403
                )
                await response(scope, receive, send)
                return

        if method in WRITE_METHODS:
            values = _header_values(scope, CSRF_HEADER.lower().encode("ascii"))
            # Reject ambiguous duplicate CSRF headers instead of trusting the
            # first or last value chosen by a particular server implementation.
            supplied = values[0] if len(values) == 1 else ""
            if len(values) > 1 or not csrf_matches(supplied, session):
                audit_log.record("csrf", actor, path, method, "denied")
                response = JSONResponse(
                    {"detail": "Valid CSRF token required."}, status_code=403
                )
                await response(scope, receive, send)
                return
            if origin_required() and not _origin_allowed(scope):
                audit_log.record("csrf", actor, path, "origin_check", "denied")
                response = JSONResponse(
                    {"detail": "Request origin is not allowed."}, status_code=403
                )
                await response(scope, receive, send)
                return

        scope.setdefault("state", {})["user"] = actor
        scope["state"]["session"] = safe_actor(actor)
        token = bind_actor(actor)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_actor(token)


class SecurityHeadersMiddleware:
    """Add conservative browser hardening headers to every HTTP response."""

    def __init__(self, app, *, content_security_policy: str | None = None):
        self.app = app
        self.csp = content_security_policy or (
            "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = cookie_settings()
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": self.csp,
            "Cache-Control": "no-store",
        }
        if settings["secure"]:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                mutable = MutableHeaders(scope=message)
                for name, value in headers.items():
                    if name.lower() not in mutable:
                        mutable[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


__all__ = [
    "EXEMPT_PATHS",
    "SecurityHeadersMiddleware",
    "UserSessionAuthMiddleware",
    "clear_session_cookies",
    "redact",
    "set_session_cookies",
]
