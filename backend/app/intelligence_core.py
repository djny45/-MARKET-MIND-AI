"""Single shared intelligence-core provider boundary.

Ollama is optional and disabled unless explicitly configured. This module only
summarizes already-computed research artifacts; it does not fetch market data,
calculate indicators, learn autonomously, or execute trades.
"""
from __future__ import annotations

import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


CORE_ID = "shared_central_intelligence"
DEFAULT_TIMEOUT_SECONDS = 8
MAX_INPUT_CHARS = 24_000
MAX_OUTPUT_CHARS = 8_000


class IntelligenceCoreError(ValueError):
    """Safe, user-facing intelligence-core configuration or provider error."""


def _configured_url() -> str | None:
    raw = os.getenv("OLLAMA_BASE_URL", "").strip()
    if not raw:
        return None
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


def intelligence_core_status() -> dict:
    """Report configured provider state without making a network request."""
    url = _configured_url()
    enabled = os.getenv("INTELLIGENCE_CORE_ENABLED", "false").strip().lower() == "true"
    model = os.getenv("OLLAMA_MODEL", "phi3").strip() or "phi3"
    return {
        "core_id": CORE_ID,
        "architecture": "one_shared_core_for_logical_worker_profiles",
        "provider": "ollama_local" if url and enabled else "none",
        "enabled": bool(url and enabled),
        "model": model if url and enabled else None,
        "status": "configured_not_health_checked" if url and enabled else "disabled_or_not_configured",
        "capabilities": {
            "research_synthesis": bool(url and enabled),
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
            "reason": "Local Ollama is disabled or not configured; deterministic report remains authoritative.",
        }
    payload = json.dumps(research, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > MAX_INPUT_CHARS:
        raise IntelligenceCoreError("Research input exceeds the configured synthesis size limit.")
    base_url = _configured_url()
    model = status["model"]
    prompt = (
        "Summarize only the supplied research JSON. Do not invent data, predictions, "
        "or recommendations. Explicitly mention missing provenance and uncertainty. "
        "Return concise plain text.\n\nRESEARCH JSON:\n" + payload
    )
    request_body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 700},
    }).encode("utf-8")
    request = Request(
        base_url + "/api/generate",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            decoded = json.loads(response.read(MAX_OUTPUT_CHARS * 2).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "status": "provider_unavailable",
            "core_id": CORE_ID,
            "provider": "ollama_local",
            "summary": None,
            "reason": "Local synthesis provider failed; deterministic report remains authoritative.",
        }
    summary = decoded.get("response")
    if not isinstance(summary, str) or not summary.strip():
        return {
            "status": "invalid_provider_response",
            "core_id": CORE_ID,
            "provider": "ollama_local",
            "summary": None,
            "reason": "Provider returned no usable text.",
        }
    return {
        "status": "completed",
        "core_id": CORE_ID,
        "provider": "ollama_local",
        "model": model,
        "summary": summary.strip()[:MAX_OUTPUT_CHARS],
        "source": "bounded_supplied_research_only",
        "deterministic_report_authoritative": True,
    }
