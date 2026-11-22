"""Non-secret environment validation for private deployments.

Returns structured findings without ever including secret values in output.
"""
from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import urlparse


def validate_environment(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    issues: list[str] = []

    if env.get("API_AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        token = env.get("API_AUTH_TOKEN", "").strip()
        if len(token) < 32:
            issues.append("API_AUTH_REQUIRED is true but API_AUTH_TOKEN is missing or shorter than 32 characters")

    origins = [
        value.strip().rstrip("/")
        for value in env.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
        if value.strip()
    ]
    if not origins:
        issues.append("FRONTEND_ORIGINS is empty")
    for origin in origins:
        if "*" in origin:
            issues.append("FRONTEND_ORIGINS must not contain wildcards")
            break
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            issues.append("FRONTEND_ORIGINS contains an invalid origin (scheme and host required)")
            break

    recovery = env.get("MARKET_MIND_STARTUP_RECOVERY", "true").strip().lower()
    if recovery not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        issues.append("MARKET_MIND_STARTUP_RECOVERY is not a recognised boolean value")

    rate_value = env.get("API_RATE_LIMIT_PER_MINUTE", "0").strip()
    try:
        if int(rate_value) < 0:
            issues.append("API_RATE_LIMIT_PER_MINUTE must be zero or positive")
    except ValueError:
        issues.append("API_RATE_LIMIT_PER_MINUTE must be an integer")

    return {
        "ok": not issues,
        "issues": issues,
        "checks": {
            "auth_required": env.get("API_AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"},
            "auth_token_configured": len(env.get("API_AUTH_TOKEN", "").strip()) >= 32,
            "frontend_origin_count": len(origins),
            "rate_limit_enabled": rate_value.isdigit() and int(rate_value) > 0,
            "startup_recovery_enabled": recovery not in {"false", "0", "no", "off"},
        },
        "secret_values_exposed": False,
    }
