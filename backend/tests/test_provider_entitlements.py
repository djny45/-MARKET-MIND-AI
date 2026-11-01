import unittest
from datetime import date, timedelta
from app.provider_entitlements import validate_provider_entitlement

class ProviderEntitlementTests(unittest.TestCase):
    def manifest(self):
        return {"provider":"Example Data Vendor","contract_reference":"contract://internal/123",
                "markets":["india","us"],"data_modes":["historical","live"],
                "entitlement_expires":(date.today()+timedelta(days=30)).isoformat(),
                "rights":{"display":True,"non_display":True,"storage":True,
                          "derived_data":True,"redistribution":True,"retention_terms_reviewed":True}}

    def test_complete_manifest_only_enters_manual_review(self):
        result=validate_provider_entitlement(self.manifest())
        self.assertEqual(result["status"],"eligible_for_manual_legal_and_technical_review")
        self.assertFalse(result["connector_activation"])
        self.assertFalse(result["legal_document_authenticated"])

    def test_missing_redistribution_right_blocks_manifest(self):
        item=self.manifest()
        item["rights"]["redistribution"]=False
        result=validate_provider_entitlement(item)
        self.assertEqual(result["status"],"blocked")
        self.assertIn("redistribution",result["missing_requirements"])

    def test_expired_entitlement_is_blocked(self):
        item=self.manifest()
        item["entitlement_expires"]=(date.today()-timedelta(days=1)).isoformat()
        self.assertIn("unexpired_entitlement",
                      validate_provider_entitlement(item)["missing_requirements"])

    def test_invalid_market_is_rejected(self):
        item=self.manifest()
        item["markets"]=["unknown"]
        with self.assertRaises(ValueError): validate_provider_entitlement(item)

if __name__ == "__main__":
    unittest.main()
