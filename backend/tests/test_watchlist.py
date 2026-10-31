import os
import tempfile
import unittest
from unittest.mock import patch

from app import watchlist


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "test.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_add_list_and_remove_symbol(self):
        result = watchlist.add_symbol("btcusd")
        self.assertEqual(result["symbol"], "BTCUSD")
        self.assertFalse(result["already_present"])
        listed = watchlist.list_symbols()
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["symbols"][0]["symbol"], "BTCUSD")
        self.assertTrue(watchlist.remove_symbol("BTCUSD"))
        self.assertFalse(watchlist.remove_symbol("BTCUSD"))

    def test_add_is_idempotent(self):
        watchlist.add_symbol("ETHUSD")
        again = watchlist.add_symbol("ethusd")
        self.assertTrue(again["already_present"])
        self.assertEqual(watchlist.list_symbols()["count"], 1)

    def test_rejects_blank_or_unsafe_symbols(self):
        for symbol in ("", " ", "BTC USD", "BTC/USDT", "<script>"):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ValueError):
                    watchlist.add_symbol(symbol)

    def test_limit_is_bounded(self):
        for symbol in ("BTCUSD", "ETHUSD", "SOLUSD"):
            watchlist.add_symbol(symbol)
        self.assertEqual(watchlist.list_symbols(2)["count"], 2)


if __name__ == "__main__":
    unittest.main()
