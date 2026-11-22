import unittest
from unittest.mock import patch

from app.autohedge_public_token_research import (
    get_public_token_prices,
    search_public_tokens,
)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class AutoHedgePublicTokenResearchTests(unittest.TestCase):
    @patch("app.autohedge_public_token_research.httpx.get")
    def test_search_uses_public_search_endpoint(self, get):
        get.return_value = Response([{"id": "mint", "symbol": "TST"}])
        self.assertEqual(search_public_tokens("test"), [{"id": "mint", "symbol": "TST"}])
        self.assertIn("/tokens/v2/search", get.call_args.args[0])

    @patch("app.autohedge_public_token_research.httpx.get")
    def test_price_uses_public_price_endpoint(self, get):
        get.return_value = Response({"mint": {"usdPrice": 1.2}})
        result = get_public_token_prices("So11111111111111111111111111111111111111112")
        self.assertIn("mint", result)
        self.assertIn("/price/v3", get.call_args.args[0])

    def test_rejects_empty_and_unsafe_mint_input(self):
        for value in ("", "mint;drop", "not-a-valid mint"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    get_public_token_prices(value)


if __name__ == "__main__":
    unittest.main()
