"""Optional per-user session authentication layered on the research API.

Disabled by default. Enable with MARKET_MIND_USER_AUTH=true and provide users
via MARKET_MIND_USERS (JSON list of {username, password_hash, role}). Password
hashes are produced by app.auth_crypto.hash_password. Only token digests are
persisted; raw session/CSRF tokens are returned to the caller once.
"""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping

from .auth_crypto import (
    generate_csrf_token,
    generate_session_token,
    hash_csrf_token,
    hash_session_token,
    verify_password,
)
from .auth_session_store import (
    create_session,
    get_session,
    initialize_auth_store,
    revoke_session,
)

ROLES = frozenset({"viewer", "analyst", "operator", "admin"})
IDLE_TTL_SECONDS = 30 * 60
ABSOLUTE_TTL_SECONDS = 12 * 60 * 60
SESSION_COOKIE = "mm_session"
CSRF_COOKIE = "mm_csrf"
CSRF_HEADER = "X-CSRF-Token"
EXEMPT_PATHS = frozenset({
    "/api/health", "/api/ready", "/api/auth/login", "/api/environment-validation",
})

_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_session_identities (
    session_token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    role TEXT NOT NULL
)
"""


def enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = dict(os.environ if environ is None else environ)
    return env.get("MARKET_MIND_USER_AUTH", "false").strip().lower() in {"1", "true", "yes", "on"}


def database_path(environ: Mapping[str, str] | None = None) -> Path:
    env = dict(os.environ if environ is None else environ)
    return Path(env.get("MARKET_MIND_DB", "./data/market_mind.db"))


def load_users(environ: Mapping[str, str] | None = None) -> dict[str, dict[str, str]]:
    """Parse user definitions; invalid entries are skipped, never trusted."""
    env = dict(os.environ if environ is None else environ)
    raw = env.get("MARKET_MIND_USERS", "").strip()
    if not raw:
        return {}
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(entries, list):
        return {}
    users: dict[str, dict[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        username = str(entry.get("username", "")).strip()
        password_hash = str(entry.get("password_hash", "")).strip()
        role = str(entry.get("role", "viewer")).strip()
        if username and password_hash and role in ROLES:
            users[username] = {"password_hash": password_hash, "role": role}
    return users


def authenticate(username: str, password: str, environ: Mapping[str, str] | None = None) -> dict[str, str] | None:
    user = load_users(environ).get(username)
    if not user or not isinstance(password, str):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"username": username, "role": user["role"]}


def _initialize_identities(path: Path) -> None:
    initialize_auth_store(path)
    with sqlite3.connect(str(path)) as connection:
        connection.executescript(_IDENTITY_SCHEMA)


def create_user_session(identity: dict[str, str], environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    path = database_path(environ)
    _initialize_identities(path)
    session_token = generate_session_token()
    csrf_token = generate_csrf_token()
    now = int(time.time())
    metadata = create_session(
        path,
        hash_session_token(session_token),
        hash_csrf_token(csrf_token),
        now=now,
        idle_ttl_seconds=IDLE_TTL_SECONDS,
        absolute_ttl_seconds=ABSOLUTE_TTL_SECONDS,
    )
    with sqlite3.connect(str(path)) as connection:
        connection.execute(
            "INSERT INTO auth_session_identities (session_token_hash, username, role) VALUES (?, ?, ?)",
            (hash_session_token(session_token), identity["username"], identity["role"]),
        )
    return {"session_token": session_token, "csrf_token": csrf_token, "identity": identity, **metadata}


def get_user_session(token: str, environ: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    if not isinstance(token, str) or not token:
        return None
    try:
        digest = hash_session_token(token)
    except ValueError:
        return None
    path = database_path(environ)
    if not path.is_file():
        return None
    session = get_session(path, digest, now=int(time.time()), idle_ttl_seconds=IDLE_TTL_SECONDS)
    if session is None:
        return None
    with sqlite3.connect(str(path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT username, role FROM auth_session_identities WHERE session_token_hash = ?",
            (digest,),
        ).fetchone()
    if row is None:
        return None
    return {
        "username": row["username"],
        "role": row["role"],
        "csrf_token_hash": session["csrf_token_hash"],
        "absolute_expires_at": session["absolute_expires_at"],
    }


def csrf_matches(supplied: str, session: dict[str, Any]) -> bool:
    if not isinstance(supplied, str):
        return False
    try:
        candidate = hash_csrf_token(supplied)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, session["csrf_token_hash"])


def revoke_user_session(token: str, environ: Mapping[str, str] | None = None) -> bool:
    if not isinstance(token, str) or not token:
        return False
    try:
        digest = hash_session_token(token)
    except ValueError:
        return False
    path = database_path(environ)
    if not path.is_file():
        return False
    return revoke_session(path, digest, now=int(time.time()))


def role_allows(role: str, required: str) -> bool:
    order = ["viewer", "analyst", "operator", "admin"]
    return role in order and required in order and order.index(role) >= order.index(required)
