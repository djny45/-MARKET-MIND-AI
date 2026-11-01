import os
import tempfile
import unittest
from unittest.mock import patch

from app.instrument_master import (
    register_provider_identifier, search_instrument_master, sync_reference_catalogue,
)


class InstrumentMasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "test.sqlite")})
        self.env.start()
        sync_reference_catalogue()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_catalogue_is_seeded_for_all_four_markets(self):
        result = search_instrument_master(limit=200)
        groups = {item["market_group"] for item in result["instruments"]}
        self.assertEqual(groups, {"india", "us", "crypto", "forex"})
        self.assertFalse(result["quotes_included"])

    def test_provider_identifier_is_namespaced_and_returned(self):
        item = search_instrument_master("EURUSD", market_group="forex")["instruments"][0]
        mapped = register_provider_identifier(
            item["instrument_id"], "example-provider", "OTC", "EURUSD"
        )
        self.assertEqual(mapped["status"], "registered")
        found = search_instrument_master("EURUSD", market_group="forex")["instruments"][0]
        self.assertEqual(found["provider_identifiers"][0]["provider"], "example-provider")

    def test_identifier_collision_updates_same_provider_key(self):
        items = search_instrument_master(limit=200)["instruments"]
        first = next(item for item in items if item["symbol"] == "EURUSD")
        second = next(item for item in items if item["symbol"] == "GBPUSD")
        register_provider_identifier(first["instrument_id"], "provider", "OTC", "PAIR-1")
        mapped = register_provider_identifier(second["instrument_id"], "provider", "OTC", "PAIR-1")
        self.assertEqual(mapped["instrument_id"], second["instrument_id"])

    def test_reject_unknown_instrument_and_bad_external_id(self):
        with self.assertRaises(KeyError):
            register_provider_identifier("missing", "provider", "venue", "X")
        item = search_instrument_master("BTCUSD")["instruments"][0]
        with self.assertRaises(ValueError):
            register_provider_identifier(item["instrument_id"], "provider", "venue", "bad id")

    def test_filters_and_validation(self):
        self.assertEqual(search_instrument_master(market_group="india", limit=200)["count"] > 0, True)
        with self.assertRaises(ValueError):
            search_instrument_master(market_group="unknown")
        with self.assertRaises(ValueError):
            search_instrument_master(limit=201)


if __name__ == "__main__":
    unittest.main()
