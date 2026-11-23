"""Authenticated reviewer access and controlled n8n import integration.

Reviewer credentials are supplied through N8N_REVIEWER_TOKENS_JSON as a JSON
object keyed by reviewer ID. Each value contains a long random token and roles.
The n8n API key and URL are server-side environment configuration only.
This module can create and inspect workflows, but has no activation or execution
operation. Import requests are one-shot to avoid duplicate workflows after timeouts.
"""
from __future__ import annotations
import hmac
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, quote
from typing import Any
import httpx
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from . import sqlite_tuning

REVIEWER_BEARER = HTTPBearer(auto_error=False, scheme_name="MarketMindReviewerToken")
ALLOWED_ROLES = {"reviewer", "importer"}

@dataclass(frozen=True)
class ReviewerPrincipal:
    reviewer_id: str
    roles: frozenset[str]

def authenticate_reviewer(credentials: HTTPAuthorizationCredentials | None) -> ReviewerPrincipal:
    """Authenticate a reviewer against configured high-entropy bearer tokens."""
    raw = os.getenv("N8N_REVIEWER_TOKENS_JSON", "").strip()
    if not raw:
        raise HTTPException(status_code=503, detail="Reviewer authentication is not configured.")
    try:
        configured = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Reviewer authentication configuration is invalid.") from exc
    if not isinstance(configured, dict):
        raise HTTPException(status_code=503, detail="Reviewer authentication configuration is invalid.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer reviewer token required.", headers={"WWW-Authenticate":"Bearer"})
    supplied = credentials.credentials
    if not isinstance(supplied, str) or len(supplied) < 32:
        raise HTTPException(status_code=401, detail="Invalid reviewer credentials.", headers={"WWW-Authenticate":"Bearer"})
    for reviewer_id, entry in configured.items():
        if not isinstance(reviewer_id, str) or not reviewer_id or len(reviewer_id) > 120 or not isinstance(entry, dict):
            continue
        expected = entry.get("token")
        roles = entry.get("roles", [])
        if not isinstance(expected, str) or len(expected) < 32 or not isinstance(roles, list):
            continue
        if hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            clean_roles = frozenset(role for role in roles if isinstance(role, str) and role in ALLOWED_ROLES)
            if not clean_roles:
                break
            return ReviewerPrincipal(reviewer_id=reviewer_id, roles=clean_roles)
    raise HTTPException(status_code=401, detail="Invalid reviewer credentials.", headers={"WWW-Authenticate":"Bearer"})

def require_role(principal: ReviewerPrincipal, role: str) -> ReviewerPrincipal:
    if role not in principal.roles:
        raise HTTPException(status_code=403, detail="Reviewer token does not grant the required role.")
    return principal

def _connect() -> sqlite3.Connection:
    path = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite_tuning.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS n8n_workflow_drafts (
        draft_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, title TEXT NOT NULL,
        workflow_json TEXT NOT NULL, workflow_sha256 TEXT NOT NULL, validation_json TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS n8n_workflow_imports (
        import_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL UNIQUE,
        requested_by TEXT NOT NULL, status TEXT NOT NULL,
        remote_workflow_id TEXT, remote_workflow_name TEXT,
        active_state_verified INTEGER NOT NULL DEFAULT 0,
        error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY(draft_id) REFERENCES n8n_workflow_drafts(draft_id))""")
    return db

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _n8n_config() -> tuple[str, str]:
    raw_url = os.getenv("N8N_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("N8N_API_KEY", "").strip()
    if not raw_url or not api_key:
        raise HTTPException(status_code=503, detail="n8n import is not configured.")
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="N8N_BASE_URL must be a trusted absolute URL without credentials, query, or fragment.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1", "n8n", "host.docker.internal"}:
        raise HTTPException(status_code=503, detail="Plain HTTP is permitted only for configured local n8n hosts.")
    if parsed.path not in {"", "/", "/api/v1"}:
        raise HTTPException(status_code=503, detail="N8N_BASE_URL must be the instance root or /api/v1.")
    base = raw_url[:-7] if parsed.path == "/api/v1" else raw_url.rstrip("/")
    return base + "/api/v1", api_key

def import_approved_workflow(draft_id: str, requested_by: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Create an approved workflow in n8n, then verify it remains inactive.

    No activation or execution API is called. A timeout is recorded as outcome_unknown
    and cannot be retried automatically because the remote create may have succeeded.
    """
    if not isinstance(requested_by, str) or not requested_by.strip() or len(requested_by) > 120:
        raise ValueError("requested_by must contain 1 to 120 characters.")
    api_base, api_key = _n8n_config()
    now = _now()
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        draft = db.execute("SELECT draft_id,title,workflow_json,workflow_sha256,status FROM n8n_workflow_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="n8n workflow draft not found.")
        if draft["status"] != "approved":
            raise HTTPException(status_code=409, detail="Only human-approved workflow drafts can be imported.")
        existing = db.execute("SELECT status,remote_workflow_id FROM n8n_workflow_imports WHERE draft_id=?", (draft_id,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="An import attempt already exists; reconcile its remote state before any retry.")
        import_id = __import__("uuid").uuid4().hex
        db.execute("INSERT INTO n8n_workflow_imports(import_id,draft_id,requested_by,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                   (import_id,draft_id,requested_by.strip(),"importing",now,now))
        workflow = json.loads(draft["workflow_json"])
        expected_hash = draft["workflow_sha256"]
    # Revalidate immediately before the external side effect and strip metadata not accepted by the public API.
    from .n8n_workflow_validation import validate_n8n_workflow
    canonical = json.dumps(workflow, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if not hmac.compare_digest(hashlib.sha256(canonical.encode("utf-8")).hexdigest(), expected_hash):
        with _connect() as db:
            db.execute("UPDATE n8n_workflow_imports SET status=?,error_code=?,updated_at=? WHERE import_id=?",
                       ("rejected_before_import","workflow_fingerprint_mismatch",_now(),import_id))
        raise HTTPException(status_code=409, detail="Workflow fingerprint changed; import blocked.")
    validation = validate_n8n_workflow(workflow)
    allowed_node_types = {"n8n-nodes-base.manualTrigger", "n8n-nodes-base.set"}
    nodes = workflow.get("nodes", [])
    unsupported = [node.get("type") for node in nodes if isinstance(node, dict) and node.get("type") not in allowed_node_types]
    if not validation.get("structurally_valid") or workflow.get("active") is not False or unsupported:
        with _connect() as db:
            db.execute("UPDATE n8n_workflow_imports SET status=?,error_code=?,updated_at=? WHERE import_id=?",
                       ("rejected_before_import","local_validation_failed",_now(),import_id))
        raise HTTPException(status_code=409, detail="Approved workflow no longer passes the restricted inactive-export validation.")
    payload = {
        "name": workflow.get("name") or draft["title"],
        "nodes": workflow.get("nodes", []),
        "connections": workflow.get("connections", {}),
        "settings": workflow.get("settings", {}),
    }
    headers = {"X-N8N-API-KEY": api_key, "Accept":"application/json", "Content-Type":"application/json"}
    own_client = client is None
    transport = client or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False)
    try:
        response = transport.post(api_base + "/workflows", json=payload, headers=headers)
        if response.status_code >= 500:
            raise TimeoutError("n8n server returned a server error; remote create outcome is uncertain.")
        if response.status_code not in {200, 201}:
            with _connect() as db:
                db.execute("UPDATE n8n_workflow_imports SET status=?,error_code=?,updated_at=? WHERE import_id=?",
                           ("rejected_by_n8n",f"http_{response.status_code}",_now(),import_id))
            raise HTTPException(status_code=502, detail="n8n rejected the workflow import.")
        try:
            created = response.json()
        except ValueError as exc:
            raise TimeoutError("n8n returned an unreadable create response; remote create outcome is uncertain.") from exc
        if isinstance(created, dict) and isinstance(created.get("data"), dict):
            created = created["data"]
        remote_id = created.get("id") if isinstance(created, dict) else None
        if not isinstance(remote_id, (str, int)) or not str(remote_id).strip():
            raise TimeoutError("n8n response did not include a workflow ID; remote create outcome is uncertain.")
        remote_id = str(remote_id)
        detail_response = transport.get(api_base + "/workflows/" + quote(remote_id, safe=""), headers=headers)
        if detail_response.status_code != 200:
            raise TimeoutError("n8n workflow was created but inactive state could not be verified.")
        remote_detail = detail_response.json()
        if isinstance(remote_detail, dict) and isinstance(remote_detail.get("data"), dict):
            remote_detail = remote_detail["data"]
        active = remote_detail.get("active") if isinstance(remote_detail, dict) else None
        if active is True:
            # Safety-only correction: never activate or publish; deactivate only if the remote API reports active.
            deactivate_response = transport.post(api_base + "/workflows/" + quote(remote_id, safe="") + "/deactivate", headers=headers)
            if deactivate_response.status_code not in {200, 204}:
                active = None
            else:
                detail_response = transport.get(api_base + "/workflows/" + quote(remote_id, safe=""), headers=headers)
                if detail_response.status_code == 200:
                    remote_detail = detail_response.json()
                    if isinstance(remote_detail, dict) and isinstance(remote_detail.get("data"), dict):
                        remote_detail = remote_detail["data"]
                    active = remote_detail.get("active") if isinstance(remote_detail, dict) else None
                else:
                    active = None
        if active is not False:
            with _connect() as db:
                db.execute("UPDATE n8n_workflow_imports SET status=?,remote_workflow_id=?,remote_workflow_name=?,active_state_verified=0,error_code=?,updated_at=? WHERE import_id=?",
                           ("imported_inactive_state_unverified",remote_id,str(remote_detail.get("name",payload["name"]))[:120],"remote_active_not_false",_now(),import_id))
            raise HTTPException(status_code=502, detail="Workflow was created, but n8n did not confirm it is inactive. Do not activate or execute it; inspect the instance manually.")
        remote_name = str(remote_detail.get("name",payload["name"]))[:120]
        with _connect() as db:
            db.execute("UPDATE n8n_workflow_imports SET status=?,remote_workflow_id=?,remote_workflow_name=?,active_state_verified=1,updated_at=? WHERE import_id=?",
                       ("imported_inactive",remote_id,remote_name,_now(),import_id))
        return {"import_id":import_id,"draft_id":draft_id,"status":"imported_inactive",
                "remote_workflow_id":remote_id,"remote_workflow_name":remote_name,
                "active_state_verified":True,"requested_by":requested_by.strip(),
                "workflow_sha256":expected_hash,"workflow_activation":False,
                "workflow_execution":False,"broker_execution":False}
    except HTTPException:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        with _connect() as db:
            db.execute("UPDATE n8n_workflow_imports SET status=?,error_code=?,updated_at=? WHERE import_id=?",
                       ("outcome_unknown",type(exc).__name__,_now(),import_id))
        raise HTTPException(status_code=502, detail="n8n import outcome is uncertain. Reconcile the n8n instance before retrying.") from exc
    finally:
        if own_client:
            transport.close()

def get_import_record(draft_id: str) -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute("SELECT import_id,draft_id,requested_by,status,remote_workflow_id,remote_workflow_name,active_state_verified,error_code,created_at,updated_at FROM n8n_workflow_imports WHERE draft_id=?", (draft_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["active_state_verified"] = bool(item["active_state_verified"])
    item["workflow_activation"] = False
    item["workflow_execution"] = False
    item["broker_execution"] = False
    return item
