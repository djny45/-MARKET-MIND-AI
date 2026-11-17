"""Optional deployment-wide bearer authentication for the research API.

Local development remains open by default. Set API_AUTH_REQUIRED=true and
API_AUTH_TOKEN to a random secret of at least 32 characters before remote use.
The health/readiness probes remain intentionally minimal and unauthenticated.
"""
from __future__ import annotations

import hmac
import os
from starlette.responses import JSONResponse


class ResearchAPIAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        required = os.getenv("API_AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        if not required or method == "OPTIONS" or path in {"/api/health", "/api/ready"}:
            await self.app(scope, receive, send)
            return

        expected = os.getenv("API_AUTH_TOKEN", "").strip()
        if len(expected) < 32:
            response = JSONResponse(
                {"detail": "API authentication is required but is not configured."},
                status_code=503,
            )
            await response(scope, receive, send)
            return

        supplied = ""
        for name, value in scope.get("headers", []):
            if name.lower() == b"authorization":
                try:
                    scheme, token = value.decode("latin-1").split(" ", 1)
                    if scheme.lower() == "bearer":
                        supplied = token.strip()
                except ValueError:
                    pass
                break

        if not supplied or not hmac.compare_digest(
            supplied.encode("utf-8"), expected.encode("utf-8")
        ):
            response = JSONResponse(
                {"detail": "Valid bearer API credentials are required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
