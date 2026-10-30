import os
import tempfile
import unittest
from unittest.mock import patch

from app.market_data import SyntheticFixtureAdapter
from app.market_store import get_bars, store_batch


class MarketStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_and_read_preserves_provenance_and_order(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("btcusd", "1d", 4)
                result = store_batch(batch)
                self.assertEqual(result["stored"], 4)
                saved = get_bars("BTCUSD", "1d", 10)
                self.assertEqual(saved["count"], 4)
                self.assertEqual(saved["bars"][0]["status"], "synthetic")
                self.assertEqual(saved["bars"][0]["source"], "synthetic-fixture")
                self.assertEqual(
                    [bar["timestamp"] for bar in saved["bars"]],
                    sorted(bar["timestamp"] for bar in saved["bars"]),
                )

    async def test_upsert_is_idempotent_for_same_source_and_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("ETHUSD", "1d", 2)
                store_batch(batch)
                store_batch(batch)
                self.assertEqual(get_bars("ETHUSD", "1d")["count"], 2)

    def test_unknown_symbol_returns_empty_history(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                result = get_bars("UNKNOWN", "1d")
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["bars"], [])


if __name__ == "__main__":
    unittest.main()
