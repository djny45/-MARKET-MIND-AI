import unittest
from app.specialist_router import route_research_brief

class SpecialistRouterTests(unittest.TestCase):
    def test_routes_data_validation_to_quality_specialist(self):
        result = route_research_brief("Validate historical market data quality and missing values")
        ids = {item["worker_id"] for item in result["candidates"]}
        self.assertTrue(ids)
        self.assertTrue(any(item["department"] == "data_quality" for item in result["candidates"]))
        self.assertEqual(result["routing_mode"], "deterministic_keyword_capability_match")

    def test_routes_crypto_and_correlation_terms(self):
        result = route_research_brief("Compare crypto bitcoin correlation with cross asset spillover")
        departments = {item["department"] for item in result["candidates"]}
        self.assertIn("crypto_markets", departments)
        self.assertIn("cross_asset", departments)

    def test_empty_match_is_explicit_not_fake(self):
        result = route_research_brief("Please summarize a neutral document about gardening")
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["candidate_count"], 0)

    def test_limit_and_input_validation(self):
        with self.assertRaises(ValueError):
            route_research_brief("")
        with self.assertRaises(ValueError):
            route_research_brief("brief", limit=0)
        with self.assertRaises(ValueError):
            route_research_brief("brief", data=object())

    def test_routing_is_deterministic(self):
        first = route_research_brief("RSI and MACD trend analysis", limit=4)
        second = route_research_brief("RSI and MACD trend analysis", limit=4)
        self.assertEqual(first["candidates"], second["candidates"])

if __name__ == "__main__":
    unittest.main()
