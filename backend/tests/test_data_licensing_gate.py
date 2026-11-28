import unittest

from app.data_licensing_gate import (
    BLOCKED,
    LICENSED_PROVIDERS,
    PENDING_LICENSE_REVIEW,
    AUTHORIZED,
    DataLicensingGate,
)


class DataLicensingGateTests(unittest.TestCase):
    def test_licensed_provider_without_review_is_pending(self):
        gate = DataLicensingGate(license_review_completed=False)
        result = gate.validate("alpha-advantage")
        self.assertEqual(result["status"], PENDING_LICENSE_REVIEW)
        self.assertFalse(result["authorized"])

    def test_licensed_provider_with_review_is_authorized(self):
        gate = DataLicensingGate(license_review_completed=True)
        self.assertEqual(gate.validate("alpha-advantage")["status"], AUTHORIZED)
        self.assertTrue(gate.validate("alpha-advantage")["authorized"])
        self.assertTrue(gate.is_authorized("alpha-advantage"))

    def test_unauthorized_sources_are_rejected(self):
        gate = DataLicensingGate(license_review_completed=True)
        for source in ("yahoo-finance-chart", "stooq", "free-web-scrapers"):
            with self.subTest(source=source):
                self.assertFalse(gate.is_authorized(source))
                self.assertEqual(gate.validate(source)["status"], BLOCKED)
                with self.assertRaises(ValueError):
                    gate.policy(source)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            DataLicensingGate().policy("made-up-provider")

    def test_manifest_reports_current_state(self):
        gate = DataLicensingGate(license_review_completed=True)
        manifest = gate.manifest()
        self.assertTrue(manifest["authorized"])
        # Public research sources added for exchange intelligence are honestly
        # pending review; they can never claim LIVE/DELAYED without attestation.
        from app.data_licensing_gate import PUBLIC_RESEARCH_SOURCES

        self.assertEqual(
            set(manifest["pending_license_review"]), set(PUBLIC_RESEARCH_SOURCES)
        )
        self.assertFalse(manifest["broker_execution"])
        self.assertTrue(manifest["research_only"])
        self.assertTrue(set(LICENSED_PROVIDERS).issubset(set(manifest["authorized"])))
        self.assertIn("tredye-live-json", manifest["unauthorized_sources"])
        self.assertIn("tredye-cfno-okx", manifest["unauthorized_sources"])


if __name__ == "__main__":
    unittest.main()
