import os
import tempfile
import unittest
from unittest.mock import patch

from app.market_data import SyntheticFixtureAdapter
from app.market_store import get_audit_events, get_bars, get_data_lineage, store_batch


class MarketStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_and_read_preserves_provenance_and_order(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("btcusd", "1d", 4)
                reversed_batch = batch.model_copy(update={"bars": list(reversed(batch.bars))})
                result = store_batch(reversed_batch)
                self.assertEqual(result["stored"], 4)
                self.assertEqual(result["ordering"], "chronological")
                self.assertEqual(result["duplicate_timestamps"], 0)
                self.assertIsNotNone(result["first_timestamp"])
                self.assertIsNotNone(result["last_timestamp"])
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

    async def test_store_batch_writes_audit_event_and_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("btcusd", "1d", 3)
                store_batch(batch)
                events = get_audit_events("BTCUSD", "1d", 10)
                self.assertEqual(events["count"], 1)
                event = events["events"][0]
                self.assertEqual(event["event_type"], "market_data_batch_stored")
                self.assertEqual(event["source"], "synthetic-fixture")
                self.assertEqual(event["observation_count"], 3)
                self.assertNotIn("close", event)
                lineage = get_data_lineage("BTCUSD", "1d")
                self.assertEqual(lineage["observation_count"], 3)
                self.assertEqual(lineage["lineage"][0]["source"], "synthetic-fixture")
                self.assertEqual(lineage["lineage"][0]["status"], "synthetic")

    async def test_each_successful_batch_is_audited_even_for_idempotent_upsert(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("ETHUSD", "1d", 2)
                store_batch(batch)
                store_batch(batch)
                self.assertEqual(get_audit_events("ETHUSD", "1d")["count"], 2)
                self.assertEqual(get_bars("ETHUSD", "1d")["count"], 2)

    def test_unknown_symbol_returns_empty_history(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                result = get_bars("UNKNOWN", "1d")
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["bars"], [])


if __name__ == "__main__":
    unittest.main()
