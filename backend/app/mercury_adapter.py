"""Inception Labs Mercury chat-completions adapter.

Uses the fixed Inception Labs HTTPS endpoint and reads credentials only from
INCEPTION_API_KEY. No provider key is stored in source or returned to callers.
"""
from __future__ import annotations

import os

API_ENDPOINT = "https://api.inceptionlabs.ai/v1/chat/completions"
DEFAULT_MODEL = "mercury-3"


def configured_mercury() -> tuple[str, str] | None:
    """Return (API key, model) when Mercury is enabled and configured."""
    enabled = os.getenv("INTELLIGENCE_CORE_ENABLED", "false").strip().lower() == "true"
    provider = os.getenv("INTELLIGENCE_CORE_PROVIDER", "mercury").strip().lower()
    api_key = os.getenv("INCEPTION_API_KEY", "").strip()
    model = os.getenv("INCEPTION_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if provider != "mercury" or not enabled or not api_key:
        return None
    return api_key, model


def build_mercury_request(api_key: str, model: str, prompt: str) -> tuple[str, bytes, dict[str, str]]:
    """Build a non-streaming request for Inception Labs Mercury."""
    import json

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode("utf-8")
    return API_ENDPOINT, body, {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
    }
