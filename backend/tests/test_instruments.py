import unittest

from app.instruments import search_instruments


class InstrumentSearchTests(unittest.TestCase):
    def test_symbol_search(self):
        result = search_instruments("AAPL")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["instruments"][0]["symbol"], "AAPL")
        self.assertFalse(result["quotes_included"])

    def test_asset_class_filter(self):
        result = search_instruments("", market="digital_assets")
        self.assertTrue(all(x["market"] == "digital_assets" for x in result["instruments"]))

    def test_name_search(self):
        result = search_instruments("Reliance")
        self.assertEqual(result["instruments"][0]["symbol"], "RELIANCE")

    def test_empty_query_limited(self):
        result = search_instruments("", limit=3)
        self.assertEqual(result["count"], 3)

    def test_four_market_groups_have_reference_instruments(self):
        expected = {"india": "RELIANCE", "us": "AAPL", "crypto": "BTCUSD", "forex": "EURUSD"}
        for group, symbol in expected.items():
            with self.subTest(group=group):
                result = search_instruments("", market_group=group)
                self.assertIn(symbol, [item["symbol"] for item in result["instruments"]])
                self.assertTrue(all(item["market_group"] == group for item in result["instruments"]))

    def test_instruments_have_stable_reference_metadata(self):
        result = search_instruments("USDINR")
        item = result["instruments"][0]
        self.assertEqual(item["instrument_id"], "forex:otc:USDINR")
        self.assertEqual(item["instrument_type"], "spot_fx")
        self.assertEqual(item["metadata_status"], "reference_only")
        self.assertFalse(item["quotes_included"])

    def test_query_can_match_venue(self):
        result = search_instruments("NASDAQ", market_group="us")
        self.assertTrue(result["instruments"])
        self.assertTrue(all("NASDAQ" in item["venue"] for item in result["instruments"]))

    def test_invalid_market_group_is_empty_at_catalogue_layer(self):
        self.assertEqual(search_instruments("", market_group="unknown")["count"], 0)


if __name__ == "__main__":
    unittest.main()
