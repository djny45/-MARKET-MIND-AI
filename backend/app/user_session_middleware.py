"""Opt-in per-user session enforcement for the research API."""
from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

from starlette.responses import JSONResponse

from .user_auth import (
    CSRF_COOKIE,
    CSRF_HEADER,
    EXEMPT_PATHS,
    SESSION_COOKIE,
    csrf_matches,
    enabled,
    get_user_session,
)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _cookies(scope: dict[str, Any]) -> SimpleCookie:
    jar: SimpleCookie = SimpleCookie()
    for name, value in scope.get("headers", []):
        if name.lower() == b"cookie":
            try:
                jar.load(value.decode("latin-1"))
            except Exception:
                pass
    return jar


class UserSessionAuthMiddleware:
    """Validate session cookies and bind CSRF tokens for write requests.

    No-ops unless MARKET_MIND_USER_AUTH is enabled, so local research and the
    existing test suite keep working without credentials.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or not enabled()
            or not scope.get("path", "").startswith("/api/")
            or scope.get("path", "") in EXEMPT_PATHS
            or scope.get("method", "GET").upper() == "OPTIONS"
        ):
            await self.app(scope, receive, send)
            return

        jar = _cookies(scope)
        token = jar[SESSION_COOKIE].value if SESSION_COOKIE in jar else ""
        session = get_user_session(token)
        if session is None:
            response = JSONResponse(
                {"detail": "Valid user session required."},
                status_code=401,
                headers={"WWW-Authenticate": "Session"},
            )
            await response(scope, receive, send)
            return

        if scope.get("method", "GET").upper() in WRITE_METHODS:
            supplied = ""
            for name, value in scope.get("headers", []):
                if name.lower() == CSRF_HEADER.lower().encode("ascii"):
                    supplied = value.decode("latin-1")
                    break
            if not csrf_matches(supplied, session):
                response = JSONResponse(
                    {"detail": "Valid CSRF token required."}, status_code=403
                )
                await response(scope, receive, send)
                return

        scope.setdefault("state", {})["user"] = {
            "username": session["username"],
            "role": session["role"],
        }
        await self.app(scope, receive, send)
