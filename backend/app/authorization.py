"""Resource-level authorization for the research API.

The model is deliberately small and deny-by-default:

* Four ordered roles: viewer < analyst < operator < admin.
* A missing/unknown actor or role is never allowed.
* Sensitive global endpoints have an explicit minimum role (see
  ``SENSITIVE_ROUTE_POLICY``).
* User-owned resources (watchlists, saved layouts, research runs/tasks and
  memory items) are tracked by ``OwnershipRegistry``: a thread-safe in-process
  cache backed by the durable ``resource_ownership`` SQLite table. A user may
  only read or mutate their own resource; admins retain an explicit override.

The project keeps local development open by default: the integration layer
(FastAPI dependencies / middleware) only enforces these rules when per-user
authentication is enabled. The primitives themselves always fail closed.
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import HTTPException, Request
from . import sqlite_tuning

ROLES: tuple[str, ...] = ("viewer", "analyst", "operator", "admin")
_ROLE_LEVELS: dict[str, int] = {role: level for level, role in enumerate(ROLES)}

# Used when a resource is created without an authenticated actor (local mode).
ANONYMOUS_OWNER = "anonymous"

# Global (non-user-owned) endpoints that are sensitive by nature. The policy is
# applied centrally by UserSessionAuthMiddleware so a newly added route under
# one of these prefixes cannot accidentally become publicly accessible.
SENSITIVE_ROUTE_POLICY: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"^/api/admin(?:/|$)"), "admin", "user_administration"),
    (re.compile(r"^/api/environment-validation/?$"), "admin", "environment_validation"),
    (re.compile(r"^/api/system/config(?:/|$)"), "admin", "system_configuration"),
    (re.compile(r"^/api/backup(?:/|$)"), "admin", "backup_restore"),
    (re.compile(r"^/api/restore(?:/|$)"), "admin", "backup_restore"),
    (re.compile(r"^/api/security(?:/|$)"), "operator", "audit_logs"),
    (
        re.compile(r"^/api/workers/[^/]+/memory/[^/]+/review/?$"),
        "operator",
        "memory_review",
    ),
    (
        re.compile(r"^/api/instrument-master/identifiers/?$"),
        "analyst",
        "instrument_identifiers",
    ),
    (re.compile(r"^/api/market-data/store/?$"), "analyst", "market_data_store"),
    (
        re.compile(r"^/api/market-data/import-csv/?$"),
        "analyst",
        "market_data_import",
    ),
    (re.compile(r"^/api/workflows/execute/?$"), "analyst", "workflow_execution"),
)


@dataclass(frozen=True)
class ResourceRef:
    """Immutable identity of a user-owned resource."""

    resource_type: str
    resource_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, str) or not self.resource_type.strip():
            raise ValueError("resource_type must be a non-empty string")
        if not isinstance(self.resource_id, str) or not self.resource_id.strip():
            raise ValueError("resource_id must be a non-empty string")

    @property
    def key(self) -> tuple[str, str]:
        return (self.resource_type.strip(), self.resource_id.strip())


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    required_role: str | None = None
    category: str | None = None


def normalize_role(role: Any) -> str | None:
    """Return a canonical role name, or ``None`` for any untrusted value."""
    if not isinstance(role, str):
        return None
    candidate = role.strip().lower()
    return candidate if candidate in _ROLE_LEVELS else None


def role_allows(role: Any, required: str) -> bool:
    """Constant-time style, deny-by-default role comparison."""
    active = normalize_role(role)
    minimum = normalize_role(required)
    if active is None or minimum is None:
        return False
    return _ROLE_LEVELS[active] >= _ROLE_LEVELS[minimum]


def is_admin(actor: Mapping[str, Any] | None) -> bool:
    return bool(actor) and role_allows(actor.get("role"), "admin")


def actor_owner(actor: Mapping[str, Any] | None) -> str:
    """Return the stable ownership id for an actor (or local anonymous mode)."""
    if not actor:
        return ANONYMOUS_OWNER
    username = actor.get("username")
    if not isinstance(username, str) or not username.strip():
        return ANONYMOUS_OWNER
    return username.strip()


def safe_actor(actor: Mapping[str, Any] | None) -> dict[str, str]:
    """Return only non-secret identity fields, suitable for audit records."""
    if not actor:
        return {"username": ANONYMOUS_OWNER, "role": "unauthenticated"}
    return {
        "username": actor_owner(actor),
        "role": normalize_role(actor.get("role")) or "unknown",
    }


class OwnershipRegistry:
    """Thread-safe mapping of ``ResourceRef`` to its owning username.

    This is an intentionally small in-process registry. In a multi-worker
    deployment the same interface can be backed by durable storage; callers
    only depend on ``record``/``owner_of``/``is_owner`` semantics.
    """

    def __init__(self) -> None:
        self._owners: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _database() -> sqlite3.Connection:
        path = os.getenv("MARKET_MIND_DB", "./data/market_mind.db")
        connection = sqlite_tuning.connect(path, timeout=5)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS resource_ownership ("
            "resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, "
            "owner TEXT NOT NULL, PRIMARY KEY(resource_type, resource_id))"
        )
        return connection

    def record(
        self,
        resource_type: str,
        resource_id: str,
        owner: str,
        *,
        overwrite: bool = False,
    ) -> None:
        ref = ResourceRef(resource_type, resource_id)
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty string")
        owner = owner.strip()
        with self._lock:
            key = ref.key
            if overwrite or key not in self._owners:
                self._owners[key] = owner
            with self._database() as db:
                if overwrite:
                    db.execute(
                        "INSERT INTO resource_ownership (resource_type,resource_id,owner) "
                        "VALUES (?,?,?) ON CONFLICT(resource_type,resource_id) "
                        "DO UPDATE SET owner=excluded.owner",
                        (ref.resource_type, ref.resource_id, owner),
                    )
                else:
                    db.execute(
                        "INSERT OR IGNORE INTO resource_ownership "
                        "(resource_type,resource_id,owner) VALUES (?,?,?)",
                        (ref.resource_type, ref.resource_id, owner),
                    )

    def owner_of(self, resource_type: str, resource_id: str) -> str | None:
        ref = ResourceRef(resource_type, resource_id)
        with self._lock:
            with self._database() as db:
                row = db.execute(
                    "SELECT owner FROM resource_ownership WHERE resource_type=? AND resource_id=?",
                    (ref.resource_type, ref.resource_id),
                ).fetchone()
            if row is not None:
                self._owners[ref.key] = row[0]
                return row[0]
            self._owners.pop(ref.key, None)
            return None

    def is_owner(
        self, actor: Mapping[str, Any] | None, resource_type: str, resource_id: str
    ) -> bool:
        owner = self.owner_of(resource_type, resource_id)
        if owner is None:
            # Unregistered resources are not globally owned; deny access.
            return False
        return bool(actor) and hmac_compare(owner, actor_owner(actor))

    def forget(self, resource_type: str, resource_id: str) -> bool:
        ref = ResourceRef(resource_type, resource_id)
        with self._lock:
            existed = self._owners.pop(ref.key, None) is not None
            with self._database() as db:
                cursor = db.execute(
                    "DELETE FROM resource_ownership WHERE resource_type=? AND resource_id=?",
                    (ref.resource_type, ref.resource_id),
                )
            return existed or cursor.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            self._owners.clear()
            with self._database() as db:
                db.execute("DELETE FROM resource_ownership")


def hmac_compare(left: str, right: str) -> bool:
    """Compare two textual values without leaking their contents via timing."""
    import hmac

    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


ownership_registry = OwnershipRegistry()

# The session middleware binds the authenticated actor for the duration of a
# request. This lets existing endpoint signatures stay unchanged while still
# stamping ownership on newly created resources.
_current_actor: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "market_mind_current_actor", default=None
)


def bind_actor(actor: Mapping[str, Any] | None):
    """Bind the current request actor; return a token for ``reset_actor``."""
    return _current_actor.set(actor)


def reset_actor(token: Any) -> None:
    _current_actor.reset(token)


def current_actor() -> Mapping[str, Any] | None:
    return _current_actor.get()


def claim_current(resource_type: str, resource_id: str, *, registry: OwnershipRegistry | None = None) -> str:
    """Stamp a newly created resource with the current actor's ownership."""
    actor = current_actor()
    owner = actor_owner(actor)
    (registry or ownership_registry).record(resource_type, resource_id, owner)
    return owner


def authorize_current(
    required_role: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    *,
    registry: OwnershipRegistry | None = None,
) -> AuthorizationDecision:
    """Authorize using the actor bound by the session middleware."""
    resource = (
        ResourceRef(resource_type or "", resource_id or "")
        if resource_type is not None and resource_id is not None
        else None
    )
    return authorize(
        current_actor(), required_role, resource=resource, registry=registry
    )


def authorize(
    actor: Mapping[str, Any] | None,
    required_role: str,
    *,
    resource: ResourceRef | None = None,
    action: str = "access",
    registry: OwnershipRegistry | None = None,
) -> AuthorizationDecision:
    """Evaluate a role + ownership decision. Always fails closed."""
    minimum = normalize_role(required_role)
    if minimum is None:
        return AuthorizationDecision(False, "unknown_required_role", required_role)
    if not actor:
        return AuthorizationDecision(False, "authentication_required", minimum)
    if not role_allows(actor.get("role"), minimum):
        return AuthorizationDecision(False, "insufficient_role", minimum)

    if resource is not None:
        store = registry or ownership_registry
        if not isinstance(resource, ResourceRef):
            return AuthorizationDecision(False, "invalid_resource", minimum)
        owner = store.owner_of(resource.resource_type, resource.resource_id)
        if owner is None:
            return AuthorizationDecision(False, "unregistered_resource", minimum)
        if not is_admin(actor) and not hmac_compare(owner, actor_owner(actor)):
            return AuthorizationDecision(False, "not_resource_owner", minimum)
    # ``action`` is intentionally not used for additional grants; it is part of
    # the decision record so the audit layer can describe what was attempted.
    return AuthorizationDecision(True, "allowed", minimum)


# Routes that are allowed to mutate state with only a ``viewer`` session.
# These are either session lifecycle operations (login/logout) or write paths
# whose only effect is on the caller's own resource, which is separately
# gated by ``OwnershipRegistry`` / ``enforce_ownership`` in the handler.
VIEWER_WRITE_ALLOWLIST: tuple[re.Pattern[str], ...] = (
    re.compile(r"^/api/auth/logout/?$"),
    re.compile(r"^/api/watchlist(?:/|$)"),
    re.compile(r"^/api/workspaces(?:/|$)"),
)


def required_role_for_path(path: str, method: str = "GET") -> tuple[str, str] | None:
    """Return ``(minimum_role, category)`` for a protected global route.

    The policy is deny-by-default for state changes: any ``POST``/``PUT``/
    ``PATCH``/``DELETE`` under ``/api/`` requires at least ``analyst`` unless
    the path is in ``VIEWER_WRITE_ALLOWLIST``. The explicit
    :data:`SENSITIVE_ROUTE_POLICY` patterns are checked first so they can raise
    the requirement to ``operator`` or ``admin``.

    Read-only routes return ``None`` here and rely on the session check in the
    middleware; that is intentional — ``viewer`` is a read role.
    """
    if not isinstance(path, str):
        return None
    upper_method = method.upper() if isinstance(method, str) else "GET"
    for pattern, role, category in SENSITIVE_ROUTE_POLICY:
        if pattern.match(path):
            # Read-only admin listings stay admin-only; no method weakens the
            # required role. This keeps the policy simple and deny-by-default.
            return role, category
    if upper_method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/api/"):
        if not any(pattern.match(path) for pattern in VIEWER_WRITE_ALLOWLIST):
            return "analyst", "state_change"
    return None


def record_ownership(
    request: Any,
    resource_type: str,
    resource_id: str,
    *,
    registry: OwnershipRegistry | None = None,
) -> str:
    """Claim a newly created resource for the current actor (or local mode)."""
    actor = getattr(getattr(request, "state", None), "user", None)
    owner = actor_owner(actor)
    (registry or ownership_registry).record(resource_type, resource_id, owner)
    return owner


def require_role(required: str):
    """FastAPI dependency for role checks on sensitive endpoints.

    Local development (user auth disabled) is intentionally not gated so the
    existing research API and test suite remain usable without credentials.
    """

    def guard(request: Request):
        from . import user_auth  # local import avoids a module import cycle

        if not user_auth.enabled():
            return None
        actor = getattr(request.state, "user", None)
        decision = authorize(actor, required)
        if not decision.allowed:
            _deny(request, decision, required, "global")
        return actor

    return guard


def require_ownership(
    resource_type: str,
    resource_id_param: str = "resource_id",
    *,
    minimum_role: str = "viewer",
    registry: OwnershipRegistry | None = None,
):
    """FastAPI dependency enforcing ownership of a path-identified resource."""

    def guard(request: Request):
        from . import user_auth  # local import avoids a module import cycle

        if not user_auth.enabled():
            return None
        actor = getattr(request.state, "user", None)
        resource_id = str(request.path_params.get(resource_id_param, ""))
        ref = ResourceRef(resource_type, resource_id)
        decision = authorize(actor, minimum_role, resource=ref, registry=registry)
        if not decision.allowed:
            _deny(request, decision, minimum_role, resource_type)
        return actor

    return guard


def _deny(request: Any, decision: AuthorizationDecision, role: str, category: str) -> None:
    try:
        from .audit_events import audit_log, record_authorization_decision

        record_authorization_decision(
            audit_log,
            getattr(getattr(request, "state", None), "user", None),
            resource=category,
            action=request.url.path if hasattr(request, "url") else "authorization",
            decision=decision,
        )
    except Exception:
        # Auditing must never turn a denied request into a server error.
        pass
    raise HTTPException(status_code=403, detail=f"Authorization denied: {decision.reason}")


__all__ = [
    "ANONYMOUS_OWNER",
    "ROLES",
    "AuthorizationDecision",
    "OwnershipRegistry",
    "ResourceRef",
    "authorize",
    "authorize_current",
    "bind_actor",
    "claim_current",
    "current_actor",
    "hmac_compare",
    "is_admin",
    "normalize_role",
    "ownership_registry",
    "record_ownership",
    "required_role_for_path",
    "require_ownership",
    "require_role",
    "reset_actor",
    "role_allows",
    "safe_actor",
]
