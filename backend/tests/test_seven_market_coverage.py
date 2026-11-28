import unittest

from app.instruments import search_instruments
from app.markets import SEVEN_MARKETS, market_catalog, seven_market_coverage


class SevenMarketCoverageTests(unittest.TestCase):
    def test_all_seven_markets_reported(self):
        report = seven_market_coverage()
        self.assertEqual(report["count"], 7)
        self.assertEqual(set(report["markets"]), set(SEVEN_MARKETS))

    def test_core_instruments_are_registered_in_reference_catalog(self):
        report = seven_market_coverage()
        for market, meta in report["markets"].items():
            with self.subTest(market=market):
                self.assertTrue(meta["core_instrument_registry"])
                self.assertTrue(all(item["registered"] for item in meta["core_instrument_registry"]))

    def test_commodity_reference_entries_are_metadata_only(self):
        for symbol in ("XAGUSD", "MCXGOLD", "MCXSILVER", "MCXCRUDE"):
            result = search_instruments(symbol)
            match = [i for i in result["instruments"] if i["symbol"] == symbol]
            self.assertTrue(match, symbol)
            self.assertEqual(match[0]["metadata_status"], "reference_only")
            self.assertFalse(match[0]["quotes_included"])

    def test_catalog_includes_coverage_without_connectivity_claim(self):
        catalog = market_catalog()
        self.assertEqual(catalog["seven_market_coverage"]["count"], 7)
        self.assertIn("No provider connectivity", catalog["seven_market_coverage"]["availability_note"])


if __name__ == "__main__":
    unittest.main()
