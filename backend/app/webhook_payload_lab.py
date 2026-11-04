"""Offline webhook payload validation lab.

This module does not expose an HTTP server, receive network requests, send
notifications, connect to TradingView, or trigger trading. It validates
example JSON payloads for safe local experimentation only.
"""
from __future__ import annotations

import json
from typing import Any

MAX_PAYLOAD_BYTES = 8_192
ALLOWED_KEYS = {"event_id", "source", "symbol", "timeframe", "message", "created_at"}
REQUIRED_KEYS = {"event_id", "source", "message"}


def validate_payload(payload: str | bytes | dict[str, Any]) -> dict[str, Any]:
    """Parse and validate a small, inert JSON event payload.

    The output is a normalized dictionary for display/logging in a local demo.
    Fields such as secret keys, URLs, destination IDs, and order instructions
    are deliberately not accepted.
    """
    if isinstance(payload, bytes):
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError("Payload exceeds maximum size")
        payload = payload.decode("utf-8")
    elif isinstance(payload, str):
        if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError("Payload exceeds maximum size")
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Payload must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    unknown = set(payload) - ALLOWED_KEYS
    missing = REQUIRED_KEYS - set(payload)
    if unknown:
        raise ValueError(f"Unsupported payload fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")

    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(value, str):
            raise ValueError(f"Field '{key}' must be a string")
        value = value.strip()
        if not value:
            raise ValueError(f"Field '{key}' cannot be empty")
        if len(value) > 512:
            raise ValueError(f"Field '{key}' is too long")
        normalized[key] = value

    if normalized["source"].lower() not in {"sample", "synthetic", "local"}:
        raise ValueError("Only sample/synthetic/local event sources are accepted")

    return normalized
