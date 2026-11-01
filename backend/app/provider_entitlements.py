"""Validate documented data-provider rights before connector implementation.

This validates an operator-supplied entitlement manifest only. It does not
authenticate documents, contact vendors, store credentials, or activate feeds.
"""
from datetime import date

MARKETS = {"india", "us", "crypto", "forex"}
MODES = {"historical", "live"}
REQUIRED_RIGHTS = {
    "display", "non_display", "storage", "derived_data",
    "redistribution", "retention_terms_reviewed",
}

def validate_provider_entitlement(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    provider = manifest.get("provider")
    contract_ref = manifest.get("contract_reference")
    if not isinstance(provider, str) or not provider.strip() or len(provider) > 120:
        raise ValueError("provider must contain 1 to 120 characters")
    if not isinstance(contract_ref, str) or not contract_ref.strip() or len(contract_ref) > 300:
        raise ValueError("contract_reference is required")
    markets = manifest.get("markets")
    modes = manifest.get("data_modes")
    if not isinstance(markets, list) or not markets or not set(markets) <= MARKETS:
        raise ValueError("markets must be a non-empty subset of india, us, crypto, forex")
    if not isinstance(modes, list) or not modes or not set(modes) <= MODES:
        raise ValueError("data_modes must be a non-empty subset of historical, live")
    expiry = manifest.get("entitlement_expires")
    try:
        expiry_date = date.fromisoformat(expiry)
    except (TypeError, ValueError) as exc:
        raise ValueError("entitlement_expires must be an ISO date YYYY-MM-DD") from exc
    rights = manifest.get("rights")
    if not isinstance(rights, dict):
        raise ValueError("rights must be an object")
    missing = sorted(key for key in REQUIRED_RIGHTS if rights.get(key) is not True)
    if expiry_date < date.today():
        missing.append("unexpired_entitlement")
    return {
        "provider": provider.strip(),
        "contract_reference": contract_ref.strip(),
        "markets": sorted(set(markets)),
        "data_modes": sorted(set(modes)),
        "entitlement_expires": expiry_date.isoformat(),
        "status": "eligible_for_manual_legal_and_technical_review" if not missing else "blocked",
        "missing_requirements": missing,
        "connector_activation": False,
        "credentials_validated": False,
        "legal_document_authenticated": False,
        "note": "Manifest fields are operator assertions, not independently verified legal evidence.",
    }
