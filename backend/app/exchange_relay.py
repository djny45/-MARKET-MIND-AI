"""Fixed, allowlisted same-origin relay for public OKX market statistics.

This is NOT a generic URL proxy. It extends the existing allowlist/SSRF-safe
pattern from ``browser_research.py``:

* Only ``www.okx.com`` is allowed, and only a fixed set of public V5 paths.
* Query parameters are validated against strict regexes; no URL is accepted
  from the caller.
* No headers, cookies, credentials or request bodies are forwarded.
* Responses pass through the existing ``provider_policy.LIMITER`` for pacing
  and bounded caching, with the upstream status and timestamps preserved.
* This module never contacts Tredye's observed endpoints.

The relay exists because some OKX statistics endpoints do not send browser
CORS headers. It is research-only and never claims a live feed.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .provider_adapters import ProviderError, USER_AGENT
from .provider_policy import LIMITER

ALLOWED_HOST = "www.okx.com"
MAX_RESPONSE_BYTES = 1_000_000
TIMEOUT_SECONDS = 8

# Fixed path -> (allowed query keys, regex validators). No caller URL is used.
ALLOWED_PATHS: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "/api/v5/public/taker-volume": (
        ("instId",), {"instId": r"^[A-Z0-9_-]{3,32}$"},
    ),
    "/api/v5/public/global-long-short-account-ratio": (
        ("instId", "period"),
        {"instId": r"^[A-Z0-9_-]{3,32}$", "period": r"^(5m|15m|1H|4H|1D)$"},
    ),
    "/api/v5/rubik/stat/taker-volume": (
        ("instId",), {"instId": r"^[A-Z0-9_-]{3,32}$"},
    ),
    "/api/v5/rubik/stat/long-short-ratio": (
        ("instId", "period"),
        {"instId": r"^[A-Z0-9_-]{3,32}$", "period": r"^(5m|15m|1H|4H|1D)$"},
    ),
    "/api/v5/market/ticker": (
        ("instId",), {"instId": r"^[A-Z0-9_-]{3,32}$"},
    ),
    "/api/v5/market/candles": (
        ("instId", "bar", "limit"),
        {
            "instId": r"^[A-Z0-9_-]{3,32}$",
            "bar": r"^(1m|5m|15m|30m|1H|2H|4H|6H|12H|1D|1W|1M)$",
            "limit": r"^\d{1,3}$",
        },
    ),
}


class RelayPolicyError(ValueError):
    """Raised when a relay request violates the fixed allowlist."""


def validate_relay_request(path: str, params: dict[str, Any]) -> tuple[str, str]:
    """Validate a caller-supplied path and params against the fixed policy."""
    if not isinstance(path, str) or path not in ALLOWED_PATHS:
        raise RelayPolicyError("path_not_allowlisted")
    allowed_keys, validators = ALLOWED_PATHS[path]
    if not isinstance(params, dict) or set(params) - set(allowed_keys):
        raise RelayPolicyError("parameter_not_allowlisted")
    query: dict[str, str] = {}
    for key, value in params.items():
        text = str(value).strip()
        pattern = validators.get(key)
        if pattern is None or not re.fullmatch(pattern, text):
            raise RelayPolicyError(f"invalid_parameter:{key}")
        query[key] = text
    encoded = urllib.parse.urlencode(query)
    url = f"https://{ALLOWED_HOST}{path}" + (f"?{encoded}" if encoded else "")
    return url, path


def _raw_fetch(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        detail = f"okx-relay returned HTTP {exc.code}"
        if retry_after:
            detail += f" (Retry-After: {retry_after}s)"
        raise ProviderError(detail) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"okx-relay request failed: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("okx-relay returned invalid JSON") from exc


def relay(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an attributed, timestamped response from a fixed OKX path."""
    from .exchange_intelligence import register_policies

    register_policies()
    url, validated_path = validate_relay_request(path, params or {})
    retrieved = datetime.now(timezone.utc).isoformat()
    try:
        payload = LIMITER.call("okx-public", ("okx-relay", url), lambda: _raw_fetch(url))
    except ProviderError as exc:
        return {
            "relay": "okx-public", "path": validated_path,
            "status": "unavailable", "status_label": "UNAVAILABLE",
            "reason": str(exc), "retrieved_at": retrieved,
            "credentials_forwarded": False,
        }
    if not isinstance(payload, dict):
        return {
            "relay": "okx-public", "path": validated_path,
            "status": "unavailable", "status_label": "UNAVAILABLE",
            "reason": "upstream response was not a JSON object",
            "retrieved_at": retrieved, "credentials_forwarded": False,
        }
    return {
        "relay": "okx-public", "path": validated_path,
        "status": "historical", "status_label": "HISTORICAL",
        "upstream_code": payload.get("code"),
        "data": payload.get("data"),
        "retrieved_at": retrieved,
        "credentials_forwarded": False,
        "note": (
            "Same-origin relay for CORS-limited public OKX endpoints. "
            "No credentials are forwarded; no live claim is made."
        ),
    }


def manifest() -> dict[str, Any]:
    return {
        "mode": "fixed_allowlist_relay",
        "allowed_host": ALLOWED_HOST,
        "allowed_paths": sorted(ALLOWED_PATHS),
        "accepts_caller_url": False,
        "credentials_forwarded": False,
        "tredye_endpoints_used": False,
        "broker_execution": False,
    }
