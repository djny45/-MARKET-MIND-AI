"""Gate for licensed live/delayed market data sources.

Authorized sources are registered here with their access model and licensing
terms. Unauthorized sources are rejected. Providers that must be reviewed can
enter a manual licensing-review window. This is the first layer of a
hypothetical licensed live integration; it does not itself connect to providers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

AUTHORIZED = "authorized"
PENDING_LICENSE_REVIEW = "pending_license_review"
BLOCKED = "blocked"


@dataclass(frozen=True)
class DataProviderPolicy:
    name: str
    endpoint: str
    requires_license: bool
    requires_license_review: bool
    authentication: str
    notes: str
    restricted_use: list[str]

    def to_record(self) -> dict:
        return asdict(self)


LICENSED_PROVIDERS: dict[str, DataProviderPolicy] = {
    "alpha-advantage": DataProviderPolicy(
        name="alpha-advantage",
        endpoint="https://www.alphavantage.co",
        requires_license=True,
        requires_license_review=True,
        authentication="apikey_bearer",
        notes="Terms and redistribution terms must be reviewed before use.",
        restricted_use=["redistribution", "company-branding", "premium_realtime"],
    ),
    "market-data-api-center": DataProviderPolicy(
        name="market-data-api-center",
        endpoint="https://marketdataapi-center.com/docs",
        requires_license=True,
        requires_license_review=False,
        authentication="apikey_bearer",
        notes="Independent REST API. Review contractual limits and pricing terms at provider.",
        restricted_use=["premium_realtime", "exchange_feeds_to_noncustomers"],
    ),
}

UNAUTHORIZED_SOURCES = frozenset({
    "yahoo-finance-chart",
    "stooq",
    "free-web-scrapers",
    "third-party-scraped-feeds",
    "unknown-custom-source",
    # Observed Tredye-owned endpoints are NOT licensed feeds for this platform.
    "tredye-live-json",
    "tredye-cfno-okx",
})

# EXTENSION: public exchange endpoints integrated for research. They are not
# licensed live feeds: access is pending review and they can never claim
# LIVE/DELAYED without operator attestation. Listing them here makes the
# provenance decision auditable instead of implicit in adapter code.
PUBLIC_RESEARCH_SOURCES: dict[str, DataProviderPolicy] = {
    name: DataProviderPolicy(
        name=name,
        endpoint="official-public-api",
        requires_license=True,
        requires_license_review=True,
        authentication="public_unauthenticated",
        notes=(
            "Public research endpoint. Attestation and licensing review are "
            "required before any live/delayed claim; no credentials are used."
        ),
        restricted_use=["redistribution", "execution", "real_money"],
    )
    for name in (
        "okx-public", "coinbase-public", "bybit-public", "kraken-public",
        "deribit-public", "hyperliquid-public", "alternative-sentiment",
        "coingecko-gold-token",
    )
}


class DataLicensingGate:
    def __init__(self, license_review_completed: bool = False):
        self.license_review_completed = license_review_completed

    def policy(self, provider: str) -> DataProviderPolicy:
        if provider in UNAUTHORIZED_SOURCES:
            raise ValueError(f"{provider} is on the unauthorized sources list")
        if provider in PUBLIC_RESEARCH_SOURCES:
            return PUBLIC_RESEARCH_SOURCES[provider]
        if provider not in LICENSED_PROVIDERS:
            raise ValueError(f"unknown provider: {provider}")
        return LICENSED_PROVIDERS[provider]

    def is_authorized(self, provider: str) -> bool:
        if provider in UNAUTHORIZED_SOURCES:
            return False
        if provider in PUBLIC_RESEARCH_SOURCES:
            # Research use is permitted; live/delayed claims still require
            # attestation and a completed licensing review.
            return False
        policy = LICENSED_PROVIDERS.get(provider)
        return policy is not None

    def validate(self, provider: str) -> dict:
        if provider in UNAUTHORIZED_SOURCES:
            return {
                "provider": provider,
                "status": BLOCKED,
                "reason": "source is not licensed for this platform",
                "authorized": False,
            }
        if provider in PUBLIC_RESEARCH_SOURCES:
            return {
                "provider": provider,
                "status": PENDING_LICENSE_REVIEW,
                "reason": (
                    "public research endpoint; historical only until attested "
                    "and license review is completed"
                ),
                "authorized": False,
                "policy": PUBLIC_RESEARCH_SOURCES[provider].to_record(),
            }
        policy = self.policy(provider)
        needs_review = policy.requires_license_review and not self.license_review_completed
        status = PENDING_LICENSE_REVIEW if needs_review else AUTHORIZED
        return {
            "provider": provider,
            "status": status,
            "authorized": not needs_review,
            "policy": policy.to_record(),
        }

    def manifest(self) -> dict:
        return {
            "license_review_completed": self.license_review_completed,
            "authorized": [
                policy.name
                for policy in LICENSED_PROVIDERS.values()
                if self.validate(policy.name)["authorized"]
            ],
            "pending_license_review": sorted(set(
                [policy.name for policy in LICENSED_PROVIDERS.values()
                 if self.validate(policy.name)["status"] == PENDING_LICENSE_REVIEW]
                + list(PUBLIC_RESEARCH_SOURCES)
            )),
            "unauthorized_sources": sorted(UNAUTHORIZED_SOURCES),
            "credentials_required": [
                policy.name
                for policy in LICENSED_PROVIDERS.values()
                if policy.authentication != "none"
            ],
            "external_calls_enabled": self.license_review_completed,
            "research_only": True,
            "broker_execution": False,
        }
