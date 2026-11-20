"""Single-owner cookie authentication endpoints and default-deny API middleware."""
from __future__ import annotations

import os
import hmac
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .auth_crypto import (
    generate_csrf_token,
    generate_session_token,
    hash_csrf_token,
    hash_session_token,
    verify_password,
    verify_csrf_token,
)
from .auth_session_store import (
    create_session,
    get_session,
    initialize_auth_store,
    revoke_session,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
SESSION_COOKIE = "market_mind_session"
CSRF_COOKIE = "market_mind_csrf"
CSRF_HEADER = "x-csrf-token"
_PUBLIC_PATHS = {"/api/health", "/api/ready", "/api/auth/login"}
_RATE_LOCK = threading.Lock()
_LOGIN_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)
_RATE_WINDOW_SECONDS = 900
_RATE_MAX_ATTEMPTS = 8
_RATE_MAX_KEYS = 4096
_RATE_OVERFLOW_KEY = "__overflow__"
_STORE_INIT_LOCK = threading.Lock()
_INITIALIZED_DATABASES: set[str] = set()


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _session_database() -> Path:
    return Path(os.getenv("MARKET_MIND_AUTH_DB", "/data/auth_sessions.sqlite3"))


def _ttl(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 60 or value > 60 * 60 * 24 * 30:
        raise RuntimeError(f"{name} must be between 60 seconds and 30 days")
    return value


def _normalize_origin(value: str) -> str | None:
    """Normalize one exact HTTP(S) origin; reject URLs with broader scope."""
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (
        scheme not in {"http", "https"}
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "*" in parsed.netloc
        or "%" in parsed.netloc
    ):
        return None
    hostname = hostname.lower()
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port == (80 if scheme == "http" else 443):
        port = None
    authority = f"{host}:{port}" if port is not None else host
    return f"{scheme}://{authority}"


def _allowed_origins() -> set[str]:
    configured = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173")
    origins: set[str] = set()
    for raw_value in configured.split(","):
        value = raw_value.strip()
        if not value:
            continue
        normalized = _normalize_origin(value)
        if normalized is None:
            raise RuntimeError(
                "FRONTEND_ORIGINS must contain only exact HTTP(S) origins "
                "without credentials, paths, query strings, fragments, or wildcards"
            )
        origins.add(normalized)
    return origins


def _check_origin(request: Request) -> bool:
    origin = _normalize_origin(request.headers.get("origin", ""))
    return bool(origin and origin in _allowed_origins())


def _client_key(request: Request) -> str:
    # Do not trust X-Forwarded-For here; the proxy must not be able to spoof
    # a client identity unless a separately trusted proxy chain is configured.
    return request.client.host if request.client else "unknown"


def _login_rate_limited(key: str, now: float | None = None) -> bool:
    current = time.monotonic() if now is None else now
    with _RATE_LOCK:
        # Bound memory even if requests arrive with many distinct client keys.
        # Remove expired buckets first; if all buckets are active, new
        # identities share a conservative overflow bucket instead of evicting
        # active limits and allowing a rate-limit bypass.
        if len(_LOGIN_ATTEMPTS) >= _RATE_MAX_KEYS:
            for stale_key, stale_attempts in list(_LOGIN_ATTEMPTS.items()):
                while stale_attempts and current - stale_attempts[0] >= _RATE_WINDOW_SECONDS:
                    stale_attempts.popleft()
                if not stale_attempts:
                    _LOGIN_ATTEMPTS.pop(stale_key, None)

        bucket_key = key
        if bucket_key not in _LOGIN_ATTEMPTS and len(_LOGIN_ATTEMPTS) >= _RATE_MAX_KEYS:
            bucket_key = _RATE_OVERFLOW_KEY

        attempts = _LOGIN_ATTEMPTS[bucket_key]
        while attempts and current - attempts[0] >= _RATE_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= _RATE_MAX_ATTEMPTS:
            return True
        attempts.append(current)
        return False


def _cookie_settings() -> dict[str, Any]:
    return {
        "httponly": True,
        "secure": _truthy("MARKET_MIND_COOKIE_SECURE", "true"),
        "samesite": "strict",
        "path": "/",
    }


def _ensure_store() -> Path:
    path = _session_database()
    key = str(path.resolve())
    if key not in _INITIALIZED_DATABASES or not path.exists():
        with _STORE_INIT_LOCK:
            if key not in _INITIALIZED_DATABASES or not path.exists():
                initialize_auth_store(path)
                _INITIALIZED_DATABASES.add(key)
    return path


def _clear_login_attempts(key: str) -> None:
    with _RATE_LOCK:
        _LOGIN_ATTEMPTS.pop(key, None)


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    if not _check_origin(request):
        raise HTTPException(status_code=403, detail="Origin not allowed")
    password_hash = os.getenv("MARKET_MIND_OWNER_PASSWORD_HASH", "")
    if not password_hash:
        raise HTTPException(status_code=503, detail="Owner authentication is not configured")
    if _login_rate_limited(_client_key(request)):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    client_key = _client_key(request)
    if not verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _clear_login_attempts(client_key)

    # Rotation must fail closed if an existing session cannot be revoked.
    # Ignore only malformed client-supplied tokens; storage errors must not
    # silently leave the previous authenticated session active.
    previous_token = request.cookies.get(SESSION_COOKIE, "")
    if previous_token:
        try:
            previous_hash = hash_session_token(previous_token)
        except ValueError:
            previous_hash = None
        if previous_hash:
            try:
                revoke_session(_ensure_store(), previous_hash, now=int(time.time()))
            except (OSError, sqlite3.Error, RuntimeError) as exc:
                raise HTTPException(
                    status_code=503, detail="Authentication storage unavailable"
                ) from exc

    now = int(time.time())
    session_ttl = _ttl("MARKET_MIND_SESSION_IDLE_TTL", 1800)
    absolute_ttl = _ttl("MARKET_MIND_SESSION_ABSOLUTE_TTL", 43200)
    session_token = generate_session_token()
    csrf_token = generate_csrf_token()
    try:
        database = _ensure_store()
        create_session(
            database,
            hash_session_token(session_token),
            hash_csrf_token(csrf_token),
            now=now,
            idle_ttl_seconds=session_ttl,
            absolute_ttl_seconds=absolute_ttl,
        )
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Authentication storage unavailable") from exc
    response = JSONResponse({"authenticated": True, "expires_in": absolute_ttl})
    settings = _cookie_settings()
    response.set_cookie(
        SESSION_COOKIE, session_token, max_age=absolute_ttl, **settings
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=absolute_ttl,
        httponly=False,
        secure=settings["secure"],
        samesite=settings["samesite"],
        path=settings["path"],
    )
    return response


@router.get("/session")
def current_session(request: Request):
    session = getattr(request.state, "auth_session", None)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {
        "authenticated": True,
        "user": "owner",
        "idle_expires_at": session["idle_expires_at"],
        "absolute_expires_at": session["absolute_expires_at"],
    }


@router.post("/logout")
def logout(request: Request):
    session_hash = getattr(request.state, "auth_session_hash", None)
    if session_hash:
        try:
            revoke_session(_ensure_store(), session_hash, now=int(time.time()))
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail="Authentication storage unavailable") from exc
    response = JSONResponse({"authenticated": False})
    settings = _cookie_settings()
    response.delete_cookie(SESSION_COOKIE, path=settings["path"], secure=settings["secure"], httponly=True, samesite=settings["samesite"])
    response.delete_cookie(CSRF_COOKIE, path=settings["path"], secure=settings["secure"], httponly=False, samesite=settings["samesite"])
    return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Protect every /api route except the explicit public health and login paths."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path in _PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        if not _truthy("MARKET_MIND_AUTH_REQUIRED", "true"):
            return await call_next(request)

        if not os.getenv("MARKET_MIND_OWNER_PASSWORD_HASH"):
            return JSONResponse(
                {"detail": "Owner authentication is not configured"},
                status_code=503,
            )

        session_token = request.cookies.get(SESSION_COOKIE, "")
        if not session_token:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        try:
            session_hash = hash_session_token(session_token)
        except ValueError:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        try:
            database = _ensure_store()
            session = get_session(
                database,
                session_hash,
                now=int(time.time()),
                idle_ttl_seconds=_ttl("MARKET_MIND_SESSION_IDLE_TTL", 1800),
            )
        except (RuntimeError, OSError, sqlite3.Error):
            return JSONResponse(
                {"detail": "Authentication storage unavailable"}, status_code=503
            )
        if not session:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)

        if request.method not in {"GET", "HEAD"}:
            if not _check_origin(request):
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
            supplied = request.headers.get(CSRF_HEADER, "")
            csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
            if not verify_csrf_token(supplied, csrf_cookie):
                return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
            try:
                if not hmac.compare_digest(hash_csrf_token(supplied), session["csrf_token_hash"]):
                    return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
            except ValueError:
                return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)

        request.state.auth_session = session
        request.state.auth_session_hash = session_hash
        return await call_next(request)
