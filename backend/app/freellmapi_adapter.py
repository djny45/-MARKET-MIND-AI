"""FreeLLMAPI-compatible OpenAI chat-completions adapter for the shared research core.

The endpoint is restricted to loopback by default to avoid turning this backend
into a credentialed proxy for arbitrary remote hosts. FreeLLMAPI itself must be
installed and configured separately; this module never stores provider secrets.
"""
from __future__ import annotations

import os
import socket
from urllib.parse import urlparse


class FreeLLMAPIConfigurationError(ValueError):
    """Invalid or unsafe FreeLLMAPI configuration."""


def configured_freellmapi() -> tuple[str, str, str] | None:
    """Return (base_url, API key, model) when fully configured; otherwise None."""
    base_url = os.getenv("FREELLMAPI_BASE_URL", "").strip()
    api_key = os.getenv("FREELLMAPI_API_KEY", "").strip()
    model = os.getenv("FREELLMAPI_MODEL", "").strip()
    enabled = os.getenv("INTELLIGENCE_CORE_ENABLED", "false").strip().lower() == "true"
    provider = os.getenv("INTELLIGENCE_CORE_PROVIDER", "ollama").strip().lower()

    if provider != "freellmapi" or not enabled:
        return None
    if not base_url or not api_key or not model:
        return None

    parsed = urlparse(base_url)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise FreeLLMAPIConfigurationError(
            "FREELLMAPI_BASE_URL must be an http URL without embedded credentials."
        )
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(
            parsed.hostname, parsed.port or 80
        )}
    except OSError as exc:
        raise FreeLLMAPIConfigurationError(
            "FreeLLMAPI host could not be resolved."
        ) from exc
    if not addresses or any(address not in {"127.0.0.1", "::1"} for address in addresses):
        raise FreeLLMAPIConfigurationError(
            "FreeLLMAPI is restricted to localhost/loopback in this integration."
        )
    return base_url.rstrip("/"), api_key, model


def build_chat_completion_request(base_url: str, api_key: str, model: str, prompt: str) -> tuple[str, bytes, dict[str, str]]:
    """Build a bounded OpenAI-compatible chat-completions request."""
    import json

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 700,
        "stream": False,
    }).encode("utf-8")
    return (
        base_url + "/v1/chat/completions",
        body,
        {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )


def extract_chat_completion_text(decoded: dict) -> str | None:
    """Extract only a standard OpenAI-compatible assistant message."""
    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) and content.strip() else None
