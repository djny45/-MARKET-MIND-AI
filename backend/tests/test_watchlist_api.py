import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import add_watchlist_symbol, delete_watchlist_symbol, get_watchlist
from app.main import WatchlistRequest


class WatchlistApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "test.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_create_list_and_delete(self):
        created = add_watchlist_symbol(WatchlistRequest(symbol="btcusd"))
        self.assertEqual(created["symbol"], "BTCUSD")
        self.assertEqual(get_watchlist()["count"], 1)
        deleted = delete_watchlist_symbol("BTCUSD")
        self.assertTrue(deleted["deleted"])
        with self.assertRaises(HTTPException) as missing:
            delete_watchlist_symbol("BTCUSD")
        self.assertEqual(missing.exception.status_code, 404)

    def test_rejects_invalid_symbol_and_limit(self):
        with self.assertRaises(HTTPException) as symbol_error:
            add_watchlist_symbol(WatchlistRequest(symbol="BTC/USDT"))
        self.assertEqual(symbol_error.exception.status_code, 400)
        with self.assertRaises(HTTPException) as limit_error:
            get_watchlist(501)
        self.assertEqual(limit_error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
