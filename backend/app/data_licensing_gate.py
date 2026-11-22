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
})


class DataLicensingGate:
    def __init__(self, license_review_completed: bool = False):
        self.license_review_completed = license_review_completed

    def policy(self, provider: str) -> DataProviderPolicy:
        if provider in UNAUTHORIZED_SOURCES:
            raise ValueError(f"{provider} is on the unauthorized sources list")
        if provider not in LICENSED_PROVIDERS:
            raise ValueError(f"unknown provider: {provider}")
        return LICENSED_PROVIDERS[provider]

    def is_authorized(self, provider: str) -> bool:
        if provider in UNAUTHORIZED_SOURCES:
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
            "pending_license_review": [
                policy.name
                for policy in LICENSED_PROVIDERS.values()
                if self.validate(policy.name)["status"] == PENDING_LICENSE_REVIEW
            ],
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
