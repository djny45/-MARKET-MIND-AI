"""Non-secret environment validation for private deployments.

Advisory by default so local research and tests remain unchanged. Setting
``ENV_VALIDATION_STRICT=1`` or ``APP_ENV=production`` turns the same checks
into an enforceable startup gate via :func:`enforce_environment`. Findings and
exceptions never contain secret values, only variable names and lengths.
"""
from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import urlparse

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class EnvironmentValidationError(RuntimeError):
    """Raised at startup when strict configuration validation fails."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("strict environment validation failed: " + "; ".join(issues))


def truthy(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in _TRUE_VALUES


def is_strict(environ: Mapping[str, str] | None = None) -> bool:
    env = dict(os.environ if environ is None else environ)
    return truthy(env.get("ENV_VALIDATION_STRICT", "")) or env.get(
        "APP_ENV", ""
    ).strip().lower() == "production"


def attested_data_sources(environ: Mapping[str, str] | None = None) -> frozenset[str]:
    """Sources explicitly cleared by the operator to claim live/delayed data."""
    env = dict(os.environ if environ is None else environ)
    raw = env.get("MARKET_MIND_ATTESTED_DATA_SOURCES", "")
    return frozenset(
        value.strip().lower()
        for value in raw.split(",")
        if value.strip()
    )


def origin_required(environ: Mapping[str, str] | None = None) -> bool:
    """Origin/Referer validation is mandatory in strict/production mode."""
    env = dict(os.environ if environ is None else environ)
    return truthy(env.get("MARKET_MIND_REQUIRE_ORIGIN", "")) or is_strict(env)


def allowed_origins(environ: Mapping[str, str] | None = None) -> list[str]:
    env = dict(os.environ if environ is None else environ)
    return [
        value.strip().rstrip("/")
        for value in env.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
        if value.strip()
    ]


def cookie_settings(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return the cookie attributes used for session and CSRF cookies."""
    env = dict(os.environ if environ is None else environ)
    samesite = env.get("MARKET_MIND_COOKIE_SAMESITE", "strict").strip().lower()
    if samesite not in {"strict", "lax", "none"}:
        samesite = "strict"
    secure = truthy(env.get("MARKET_MIND_SECURE_COOKIES", "")) or is_strict(env)
    return {
        "httponly": True,
        "samesite": samesite,
        "secure": secure,
    }


def trusted_proxy_settings(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return explicit trusted-proxy settings (zero by default = no trust)."""
    env = dict(os.environ if environ is None else environ)
    try:
        count = int(env.get("MARKET_MIND_TRUSTED_PROXY_COUNT", "0").strip())
    except (TypeError, ValueError):
        count = 0
    header = env.get("MARKET_MIND_TRUSTED_PROXY_HEADER", "x-forwarded-for").strip().lower()
    if header not in {"x-forwarded-for", "x-real-ip"}:
        header = "x-forwarded-for"
    return {"count": max(0, count), "header": header}


def validate_environment(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return structured findings; never include secret values in output."""
    env = dict(os.environ if environ is None else environ)
    issues: list[str] = []
    strict = is_strict(env)

    auth_required = truthy(env.get("API_AUTH_REQUIRED", ""))
    token = env.get("API_AUTH_TOKEN", "").strip()
    token_long_enough = len(token) >= 32
    if auth_required and not token_long_enough:
        issues.append(
            "API_AUTH_REQUIRED is true but API_AUTH_TOKEN is missing or shorter than 32 characters"
        )
    if strict:
        if not auth_required:
            issues.append("API_AUTH_REQUIRED must be true in production/strict mode")
        if not token_long_enough:
            issues.append("API_AUTH_TOKEN must be at least 32 characters in production/strict mode")

    origins = allowed_origins(env)
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
    cookies = cookie_settings(env)
    if cookies["samesite"] == "none" and not cookies["secure"]:
        issues.append("SameSite=None cookies require MARKET_MIND_SECURE_COOKIES=true")
    if strict:
        if not truthy(env.get("MARKET_MIND_SECURE_COOKIES", "")):
            issues.append("MARKET_MIND_SECURE_COOKIES must be true in production/strict mode")
        if cookies["samesite"] not in {"strict", "lax"}:
            issues.append("MARKET_MIND_COOKIE_SAMESITE must be strict or lax in production/strict mode")
        if not origin_required(env):
            issues.append("MARKET_MIND_REQUIRE_ORIGIN must be true in production/strict mode")

    recovery = env.get("MARKET_MIND_STARTUP_RECOVERY", "true").strip().lower()
    if recovery not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        issues.append("MARKET_MIND_STARTUP_RECOVERY is not a recognised boolean value")

    rate_value = env.get("API_RATE_LIMIT_PER_MINUTE", "0").strip()
    rate_limit = 0
    try:
        rate_limit = int(rate_value)
        if rate_limit < 0:
            issues.append("API_RATE_LIMIT_PER_MINUTE must be zero or positive")
    except ValueError:
        issues.append("API_RATE_LIMIT_PER_MINUTE must be an integer")
    proxy = trusted_proxy_settings(env)
    if "MARKET_MIND_TRUSTED_PROXY_COUNT" in env:
        try:
            if int(env["MARKET_MIND_TRUSTED_PROXY_COUNT"].strip()) < 0:
                issues.append("MARKET_MIND_TRUSTED_PROXY_COUNT must be zero or positive")
        except (TypeError, ValueError):
            issues.append("MARKET_MIND_TRUSTED_PROXY_COUNT must be an integer")
    if strict and proxy["count"] > 4:
        issues.append("MARKET_MIND_TRUSTED_PROXY_COUNT must be at most 4 in production/strict mode")

    return {
        "ok": not issues,
        "issues": issues,
        "strict_mode": strict,
        "checks": {
            "auth_required": auth_required,
            "auth_token_configured": token_long_enough,
            "frontend_origin_count": len(origins),
            "rate_limit_enabled": rate_limit > 0,
            "startup_recovery_enabled": recovery not in {"false", "0", "no", "off"},
            "secure_cookies": cookies["secure"],
            "cookie_samesite": cookies["samesite"],
            "trusted_proxy_count": proxy["count"],
            "trusted_proxy_header": proxy["header"],
            "origin_required": origin_required(env),
        },
        "secret_values_exposed": False,
    }


def enforce_environment(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Raise :class:`EnvironmentValidationError` when strict checks fail."""
    result = validate_environment(environ)
    if result["strict_mode"] and result["issues"]:
        raise EnvironmentValidationError(result["issues"])
    return result


__all__ = [
    "EnvironmentValidationError",
    "attested_data_sources",
    "allowed_origins",
    "cookie_settings",
    "enforce_environment",
    "is_strict",
    "origin_required",
    "trusted_proxy_settings",
    "truthy",
    "validate_environment",
]
