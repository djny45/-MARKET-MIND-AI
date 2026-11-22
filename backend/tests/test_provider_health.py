import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.data_licensing_gate import DataLicensingGate
from app.market_data import DataStatus
from app.provider_health import (
    DEGRADED,
    FRESH,
    HEALTHY,
    STALE,
    UNAVAILABLE,
    ProviderHealthRegistry,
)


def batch(source="synthetic-fixture", status=DataStatus.SYNTHETIC, age_seconds=10, warnings=None):
    return SimpleNamespace(
        source=source,
        status=status,
        retrieved_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
        warnings=warnings or [],
    )


class ProviderHealthTests(unittest.TestCase):
    def test_successful_batch_is_recorded_with_freshness(self):
        registry = ProviderHealthRegistry()
        registry.record_success(batch())
        report = registry.report()
        provider = report["providers"][0]
        self.assertEqual(provider["status"], "synthetic")
        self.assertEqual(provider["freshness"], FRESH)
        self.assertEqual(provider["observations"], 1)
        self.assertTrue(report["research_only"])
        self.assertFalse(report["broker_execution"])

    def test_stale_batch_is_marked_stale_and_degraded(self):
        registry = ProviderHealthRegistry()
        registry.record_success(batch(status=DataStatus.HISTORICAL, age_seconds=9 * 24 * 3600))
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["freshness"], STALE)
        self.assertEqual(provider["health"], DEGRADED)

    def test_missing_metadata_is_unknown_not_healthy(self):
        registry = ProviderHealthRegistry()
        registry.register("unknown-source")
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["freshness"], "unknown")
        self.assertEqual(provider["health"], DEGRADED)

    def test_failures_degrade_then_mark_unavailable(self):
        registry = ProviderHealthRegistry()
        registry.record_failure("alpha-advantage", "HTTP 500")
        self.assertEqual(registry.report()["providers"][0]["health"], DEGRADED)
        registry.record_failure("alpha-advantage", "HTTP 500")
        registry.record_failure("alpha-advantage", "HTTP 500")
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["health"], UNAVAILABLE)
        self.assertEqual(provider["consecutive_failures"], 3)

    def test_licensing_status_is_reported(self):
        registry = ProviderHealthRegistry(DataLicensingGate(license_review_completed=False))
        registry.record_success(batch(source="alpha-advantage", status=DataStatus.HISTORICAL))
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["licensing"]["status"], "pending_license_review")
        self.assertFalse(provider["licensing"]["authorized"])

    def test_success_resets_failure_counter(self):
        registry = ProviderHealthRegistry()
        registry.record_failure("synthetic-fixture", "boom")
        registry.record_success(batch())
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["consecutive_failures"], 0)
        self.assertEqual(provider["health"], DEGRADED)  # synthetic never a healthy live feed

    def test_live_fixture_within_threshold_is_healthy(self):
        registry = ProviderHealthRegistry()
        registry.record_success(batch(source="licensed-provider", status=DataStatus.LIVE, age_seconds=5))
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["freshness"], FRESH)
        self.assertEqual(provider["health"], HEALTHY)

    def test_invalid_registration_rejected(self):
        with self.assertRaises(ValueError):
            ProviderHealthRegistry().register("   ")


if __name__ == "__main__":
    unittest.main()
