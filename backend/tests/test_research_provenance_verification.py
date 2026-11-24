"""Cross-module evidence that stored research data keeps provenance limits."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar, status_allowed_for_source
from app.market_data_validation import validate_market_data_payload
from app.main import app
from app.provider_health import DEGRADED, FRESH, HEALTHY, STALE, UNAVAILABLE, ProviderHealthRegistry


def _batch(*, status=DataStatus.HISTORICAL, source="manual-review", age_seconds=60):
    retrieved_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    bar_time = retrieved_at - timedelta(days=1)
    return MarketDataBatch(
        symbol="AAPL", interval="1d", status=status, source=source,
        retrieved_at=retrieved_at, warnings=["partial-session"],
        bars=[OHLCVBar(
            timestamp=bar_time, open=10, high=12, low=9, close=11, volume=100,
        )],
    )


class ProvenanceVerificationTests(unittest.TestCase):
    def test_validation_preserves_source_status_and_freshness_disclaimer(self):
        batch = _batch()
        report = validate_market_data_payload(batch.model_dump(mode="json"))
        self.assertTrue(report["valid"])
        self.assertEqual(report["source"], "manual-review")
        self.assertEqual(report["status"], "historical")
        self.assertEqual(report["retrieved_at"], batch.retrieved_at.isoformat())
        self.assertEqual(report["warnings"], ["partial-session"])
        self.assertTrue(any("freshness" in note for note in report["limitations"]))
        self.assertTrue(any("authenticate" in note for note in report["limitations"]))

    def test_stale_historical_batch_is_detected_with_exact_age(self):
        registry = ProviderHealthRegistry()
        registry.record_success(_batch(age_seconds=9 * 24 * 3600))
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["freshness"], STALE)
        self.assertEqual(provider["health"], DEGRADED)
        self.assertGreater(provider["age_seconds"], 7 * 24 * 3600)

    def test_report_uses_the_injected_clock_for_freshness_and_health(self):
        reference = datetime.now(timezone.utc)
        registry = ProviderHealthRegistry()
        registry.record_success(_batch(age_seconds=10))
        fresh = registry.report(now=reference)["providers"][0]
        self.assertEqual(fresh["freshness"], FRESH)
        self.assertEqual(fresh["health"], HEALTHY)
        stale = registry.report(now=reference + timedelta(days=30))["providers"][0]
        self.assertEqual(stale["freshness"], STALE)
        self.assertEqual(stale["health"], DEGRADED)

    def test_provider_failures_are_recorded_without_live_claims(self):
        registry = ProviderHealthRegistry()
        for _ in range(3):
            registry.record_failure("provider-x", "HTTP 500")
        provider = registry.report()["providers"][0]
        self.assertEqual(provider["health"], UNAVAILABLE)
        self.assertEqual(provider["consecutive_failures"], 3)
        report = registry.report()
        self.assertFalse(report["broker_execution"])
        self.assertEqual(report["live_provider_activation"],
                         "requires_license_review_and_operator_approval")

    def test_live_and_delayed_labels_require_operator_attestation(self):
        self.assertFalse(status_allowed_for_source(DataStatus.LIVE, "manual-review"))
        self.assertFalse(status_allowed_for_source(DataStatus.DELAYED, "manual-review"))
        self.assertTrue(status_allowed_for_source(
            DataStatus.LIVE, "licensed-vendor",
            attested_sources=frozenset({"licensed-vendor"}),
        ))
        self.assertFalse(status_allowed_for_source(DataStatus.LIVE, "synthetic-fixture"))

    def test_invalid_payload_is_rejected_without_imputed_values(self):
        payload = _batch().model_dump(mode="json")
        payload["bars"][0]["open"] = float("nan")
        report = validate_market_data_payload(payload)
        self.assertFalse(report["valid"])
        self.assertIsNone(report["bar_count"])
        self.assertIsNone(report["source"])
        self.assertGreater(report["error_count"], 0)

    def test_provider_status_endpoint_claims_no_live_provider(self):
        response = TestClient(app).get("/api/providers/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "no_live_provider_configured")
        self.assertEqual(body["live_providers"], [])
        self.assertEqual(body["available_adapters"][0]["data_status"], "synthetic")
        self.assertIn("No live or delayed", body["market_data_note"])


if __name__ == "__main__":
    unittest.main()
