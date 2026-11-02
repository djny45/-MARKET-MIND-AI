"""Single shared intelligence-core provider boundary.

The core can use local Ollama or a loopback FreeLLMAPI OpenAI-compatible gateway.
It only summarizes already-computed research artifacts; it does not fetch market
data, calculate indicators, learn autonomously, or execute trades.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .freellmapi_adapter import (
    FreeLLMAPIConfigurationError,
    configured_freellmapi,
    build_chat_completion_request,
    extract_chat_completion_text,
)

CORE_ID = "shared_central_intelligence"
DEFAULT_TIMEOUT_SECONDS = 8
MAX_INPUT_CHARS = 24_000
MAX_OUTPUT_CHARS = 8_000


class IntelligenceCoreError(ValueError):
    """Safe, user-facing intelligence-core configuration or provider error."""


def _ollama_url() -> str | None:
    # Preserve the existing Ollama integration for backwards compatibility.
    raw = os.getenv("OLLAMA_BASE_URL", "").strip()
    if not raw:
        return None
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(raw)
    if parsed.scheme != "http" or not parsed.hostname:
        raise IntelligenceCoreError("OLLAMA_BASE_URL must be an http URL on loopback.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 80)}
    except OSError as exc:
        raise IntelligenceCoreError("Ollama host could not be resolved.") from exc
    if not addresses or any(address not in {"127.0.0.1", "::1"} for address in addresses):
        raise IntelligenceCoreError("Ollama is restricted to localhost/loopback for this milestone.")
    return raw.rstrip("/")


# Compatibility alias for existing Ollama tests and integrations.
def _configured_url() -> str | None:
    return _ollama_url()


def intelligence_core_status() -> dict:
    """Report configured provider state without making a network request."""
    enabled = os.getenv("INTELLIGENCE_CORE_ENABLED", "false").strip().lower() == "true"
    selected = os.getenv("INTELLIGENCE_CORE_PROVIDER", "ollama").strip().lower()
    try:
        free_config = configured_freellmapi()
    except FreeLLMAPIConfigurationError as exc:
        raise IntelligenceCoreError(str(exc)) from exc

    if selected == "freellmapi":
        configured = bool(enabled and free_config)
        provider = "freellmapi_local" if configured else "none"
        model = free_config[2] if configured and free_config else None
    else:
        ollama_url = _ollama_url()
        configured = bool(enabled and ollama_url)
        provider = "ollama_local" if configured else "none"
        model = (os.getenv("OLLAMA_MODEL", "phi3").strip() or "phi3") if configured else None

    return {
        "core_id": CORE_ID,
        "architecture": "one_shared_core_for_logical_worker_profiles",
        "provider": provider,
        "enabled": configured,
        "model": model,
        "status": "configured_not_health_checked" if configured else "disabled_or_not_configured",
        "capabilities": {
            "research_synthesis": configured,
            "worker_specific_models": False,
            "autonomous_learning": False,
            "market_data_fetch": False,
            "broker_execution": False,
        },
    }


def synthesize_research(research: dict, *, opener=urlopen) -> dict:
    """Optional bounded synthesis over supplied research JSON, with explicit fallback."""
    status = intelligence_core_status()
    if not status["enabled"]:
        return {
            "status": "not_configured",
            "core_id": CORE_ID,
            "provider": "none",
            "summary": None,
            "reason": "Shared AI provider is disabled or not configured; deterministic report remains authoritative.",
        }

    payload = json.dumps(research, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > MAX_INPUT_CHARS:
        raise IntelligenceCoreError("Research input exceeds the configured synthesis size limit.")
    prompt = (
        "Summarize only the supplied research JSON. Do not invent data, predictions, "
        "or recommendations. Explicitly mention missing provenance and uncertainty. "
        "Return concise plain text.

RESEARCH JSON:
" + payload
    )

    selected = os.getenv("INTELLIGENCE_CORE_PROVIDER", "ollama").strip().lower()
    if selected == "freellmapi":
        try:
            config = configured_freellmapi()
        except FreeLLMAPIConfigurationError as exc:
            raise IntelligenceCoreError(str(exc)) from exc
        if not config:
            return {
                "status": "not_configured", "core_id": CORE_ID, "provider": "none",
                "summary": None, "reason": "FreeLLMAPI settings are incomplete.",
            }
        base_url, api_key, model = config
        endpoint, body, headers = build_chat_completion_request(base_url, api_key, model, prompt)
        provider_name = "freellmapi_local"
    else:
        base_url = _ollama_url()
        model = status["model"]
        body = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0, "num_predict": 700},
        }).encode("utf-8")
        endpoint = base_url + "/api/generate"
        headers = {"Content-Type": "application/json"}
        provider_name = "ollama_local"

    request = Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with opener(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            decoded = json.loads(response.read(MAX_OUTPUT_CHARS * 2).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {
            "status": "provider_unavailable", "core_id": CORE_ID,
            "provider": provider_name, "summary": None,
            "reason": "Shared synthesis provider failed; deterministic report remains authoritative.",
        }

    summary = extract_chat_completion_text(decoded) if selected == "freellmapi" else decoded.get("response")
    if not isinstance(summary, str) or not summary.strip():
        return {
            "status": "invalid_provider_response", "core_id": CORE_ID,
            "provider": provider_name, "summary": None,
            "reason": "Provider returned no usable text.",
        }
    return {
        "status": "completed", "core_id": CORE_ID, "provider": provider_name,
        "model": model, "summary": summary.strip()[:MAX_OUTPUT_CHARS],
        "source": "bounded_supplied_research_only",
        "deterministic_report_authoritative": True,
    }
