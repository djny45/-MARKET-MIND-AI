import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import (
    ProviderIdentifierRequest, add_provider_identifier, instrument_master,
)


class InstrumentMasterApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "test.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_reference_search_and_provider_mapping(self):
        result = instrument_master("", "india", "equities", 50)
        self.assertGreater(result["count"], 0)
        self.assertTrue(all(item["market_group"] == "india" for item in result["instruments"]))
        item = result["instruments"][0]
        mapped = add_provider_identifier(ProviderIdentifierRequest(
            instrument_id=item["instrument_id"], provider="test-provider",
            venue=item["venue"], external_id="TEST-123",
        ))
        self.assertEqual(mapped["status"], "registered")
        self.assertFalse(mapped["quotes_included"])

    def test_invalid_filters_and_unknown_instrument(self):
        with self.assertRaises(HTTPException) as bad_filter:
            instrument_master("", "mars", None, 20)
        self.assertEqual(bad_filter.exception.status_code, 400)
        with self.assertRaises(HTTPException) as missing:
            add_provider_identifier(ProviderIdentifierRequest(
                instrument_id="missing", provider="provider",
                venue="venue", external_id="ID-1",
            ))
        self.assertEqual(missing.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
