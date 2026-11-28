"""Cloud-only model tier assignments for the 550 logical research agents.

The first 20 profiles (one division lead per configured department) receive the
premium model. The remaining 530 receive the standard model. This module only
resolves policy and configuration; it does not claim that credentials or model
endpoints are configured or that an inference request has succeeded.
"""
from __future__ import annotations

import os

SENIOR_AGENT_IDS = frozenset(f"worker_{index:03d}" for index in range(1, 21))
AGENT_COUNT = 550
CLOUD_PROVIDER = "mercury"


class ModelAccessConfigurationError(ValueError):
    """Raised when cloud-only model access is misconfigured."""


def model_assignment(agent_id: str, environ=None) -> dict:
    """Resolve an agent's immutable tier and configured cloud model name."""
    env = os.environ if environ is None else environ
    if not isinstance(agent_id, str) or not agent_id.startswith("worker_"):
        raise ValueError("agent_id must identify a registered worker")
    try:
        index = int(agent_id.removeprefix("worker_"))
    except ValueError as exc:
        raise ValueError("agent_id must identify a registered worker") from exc
    if index < 1 or index > AGENT_COUNT or agent_id != f"worker_{index:03d}":
        raise ValueError("agent_id must identify a registered worker")

    provider = str(env.get("MARKET_MIND_MODEL_PROVIDER", CLOUD_PROVIDER)).strip().lower()
    if provider != CLOUD_PROVIDER:
        raise ModelAccessConfigurationError(
            "Only the approved cloud provider 'mercury' is supported; local model providers are disabled."
        )

    tier = "premium" if agent_id in SENIOR_AGENT_IDS else "standard"
    model_env = "MARKET_MIND_PREMIUM_MODEL" if tier == "premium" else "MARKET_MIND_BASIC_MODEL"
    model = str(env.get(model_env, "")).strip()
    api_key_configured = bool(str(env.get("INCEPTION_API_KEY", "")).strip())
    enabled = str(env.get("INTELLIGENCE_CORE_ENABLED", "false")).strip().lower() == "true"

    return {
        "agent_id": agent_id,
        "tier": tier,
        "provider": CLOUD_PROVIDER,
        "model": model or None,
        "configured": bool(enabled and api_key_configured and model),
        "credential_configured": api_key_configured,
        "tier_env": model_env,
        "inference_enabled": False,
        "note": "Assignment metadata only; inference is enabled only after the cloud gateway invokes the configured provider.",
    }


def model_tier_manifest(environ=None) -> dict:
    """Return non-secret tier coverage and configuration readiness."""
    env = os.environ if environ is None else environ
    premium_model = str(env.get("MARKET_MIND_PREMIUM_MODEL", "")).strip()
    basic_model = str(env.get("MARKET_MIND_BASIC_MODEL", "")).strip()
    key_configured = bool(str(env.get("INCEPTION_API_KEY", "")).strip())
    enabled = str(env.get("INTELLIGENCE_CORE_ENABLED", "false")).strip().lower() == "true"
    provider = str(env.get("MARKET_MIND_MODEL_PROVIDER", CLOUD_PROVIDER)).strip().lower()
    provider_valid = provider == CLOUD_PROVIDER
    return {
        "provider": provider if provider_valid else "unsupported",
        "cloud_only": True,
        "senior_agent_count": len(SENIOR_AGENT_IDS),
        "standard_agent_count": AGENT_COUNT - len(SENIOR_AGENT_IDS),
        "premium_model_configured": bool(premium_model),
        "standard_model_configured": bool(basic_model),
        "credential_configured": key_configured,
        "gateway_enabled": enabled,
        "ready": bool(provider_valid and premium_model and basic_model and key_configured and enabled),
        "inference_enabled": False,
        "note": "Readiness reports configuration presence only; a provider health check and successful request are still required.",
    }
