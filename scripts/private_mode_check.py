#!/usr/bin/env python3
"""Secret-free preflight for a private research-only deployment.

Checks the operator-supplied environment for the invariants required before the
private platform is used: per-user auth with hashed credentials, explicit
loopback/private origins, Origin enforcement and the checked-in loopback-only
Compose perimeter. It never prints values, never calls external services and
does not certify public deployment or any external drill.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dr_common import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "backend"))
from app.env_validation import allowed_origins, is_strict, truthy  # noqa: E402

PRIVATE_SUFFIXES = (".local", ".internal", ".invalid", ".test")
ROLES = frozenset({"viewer", "analyst", "operator", "admin"})


def _private_hostname(host: str) -> bool:
    host = host.strip().lower().rstrip(".")
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or address.is_private or address.is_link_local
    except ValueError:
        pass
    return host.endswith(PRIVATE_SUFFIXES)


def _users(env: dict[str, str]) -> tuple[list[dict], list[str]]:
    raw = env.get("MARKET_MIND_USERS", "").strip()
    findings: list[str] = []
    if not raw:
        return [], ["MARKET_MIND_USERS is empty"]
    try:
        entries = json.loads(raw)
    except ValueError:
        return [], ["MARKET_MIND_USERS is not valid JSON"]
    if not isinstance(entries, list):
        return [], ["MARKET_MIND_USERS must be a JSON list"]
    for entry in entries:
        if not isinstance(entry, dict):
            findings.append("MARKET_MIND_USERS entry is not an object")
            continue
        if "password" in entry:
            findings.append("plaintext password field in MARKET_MIND_USERS")
        username = str(entry.get("username", "")).strip()
        role = str(entry.get("role", "")).strip()
        digest = str(entry.get("password_hash", "")).strip()
        if not username:
            findings.append("user entry has no username")
        if role not in ROLES:
            findings.append("user entry has an invalid role")
        if not digest.startswith("scrypt$"):
            findings.append("user entry has no scrypt password hash")
    if not any(isinstance(e, dict) and e.get("role") == "admin" for e in entries):
        findings.append("at least one admin user is required")
    return [e for e in entries if isinstance(e, dict)], findings


def check_private_mode(environ: dict[str, str] | None = None) -> dict:
    env = dict(os.environ if environ is None else environ)
    findings: list[str] = []
    checks: list[dict] = []

    def record(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "status": "pass" if ok else "fail", "detail": detail})
        if not ok:
            findings.append(f"{check_id}: {detail}")

    enabled = truthy(env.get("MARKET_MIND_USER_AUTH", "")) or is_strict(env)
    record("user_auth_enabled", enabled, "per-user sessions must be enabled")

    users, user_findings = _users(env)
    record("hashed_users", not user_findings and bool(users),
           f"{len(users)} configured user(s)" + ("; " + "; ".join(user_findings) if user_findings else ""))

    origins = allowed_origins(env)
    origin_findings: list[str] = []
    if not origins:
        origin_findings.append("FRONTEND_ORIGINS is empty")
    for origin in origins:
        parsed = urlparse(origin)
        if "*" in origin or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            origin_findings.append("FRONTEND_ORIGINS contains a wildcard or invalid origin")
        elif not _private_hostname(parsed.hostname):
            origin_findings.append("FRONTEND_ORIGINS contains a non-private host")
    record("private_origins", not origin_findings,
           f"{len(origins)} explicit origin(s)" + ("; " + "; ".join(origin_findings) if origin_findings else ""))

    enforced = truthy(env.get("MARKET_MIND_REQUIRE_ORIGIN", "")) or is_strict(env)
    record("origin_enforcement", enforced, "Origin/Referer checks on writes")

    # Static perimeter check; no host/network operation is performed.
    import config_preflight
    perimeter = config_preflight.build_report(REPO_ROOT)
    perimeter_ok = perimeter["status"] == "pass"
    record("loopback_only_perimeter", perimeter_ok,
           "checked-in Compose perimeter" if perimeter_ok else "static preflight failed")

    return {
        "status": "pass" if not findings else "fail",
        "scope": "private_research_mode_static_preflight",
        "public_ingress": "disabled",
        "external_verification": "not_claimed",
        "live_execution": "verified_at_runtime_by_api_health_and_ready",
        "values_exposed": False,
        "checks": checks,
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    report = check_private_mode()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
