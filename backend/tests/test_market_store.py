import os
import tempfile
import unittest
from unittest.mock import patch

from datetime import datetime, timezone

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar, SyntheticFixtureAdapter
from app.market_store import (get_audit_events, get_bars, get_data_lineage, get_market_overview, get_stored_return_heatmap, store_batch)


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

    def test_equivalent_timezone_offsets_upsert_as_one_utc_instant(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                retrieval = datetime(2026, 1, 2, tzinfo=timezone.utc)
                first = MarketDataBatch(
                    symbol="OFFSET", interval="1d", status=DataStatus.HISTORICAL,
                    source="provider", retrieved_at=retrieval,
                    bars=[OHLCVBar(
                        timestamp=datetime.fromisoformat("2026-01-01T05:30:00+05:30"),
                        open=10, high=12, low=9, close=11, volume=100,
                    )],
                )
                equivalent = MarketDataBatch(
                    symbol="OFFSET", interval="1d", status=DataStatus.HISTORICAL,
                    source="provider", retrieved_at=retrieval,
                    bars=[OHLCVBar(
                        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        open=10, high=13, low=9, close=12, volume=120,
                    )],
                )
                first_result = store_batch(first)
                second_result = store_batch(equivalent)
                self.assertEqual(first_result["first_timestamp"], "2026-01-01T00:00:00+00:00")
                self.assertEqual(second_result["last_timestamp"], "2026-01-01T00:00:00+00:00")
                saved = get_bars("OFFSET", "1d")
                self.assertEqual(saved["count"], 1)
                self.assertEqual(saved["timestamp_count"], 1)
                self.assertEqual(saved["bars"][0]["timestamp"], "2026-01-01T00:00:00+00:00")
                self.assertEqual(saved["bars"][0]["close"], 12)

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

    def test_existing_database_receives_heatmap_interval_index(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "existing.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}):
                get_bars("BTCUSD", "1d")
                import sqlite3
                with sqlite3.connect(database) as connection:
                    indexes = {
                        row[0] for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='index'"
                        ).fetchall()
                    }
                self.assertIn("idx_market_bars_interval_timestamp", indexes)

    def test_existing_database_receives_schema_migration_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "existing.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}):
                get_bars("BTCUSD", "1d")
                import sqlite3
                with sqlite3.connect(database) as connection:
                    version = connection.execute(
                        "SELECT MAX(version) FROM schema_migrations"
                    ).fetchone()[0]
                self.assertEqual(version, 1)

    async def test_local_market_overview_summarizes_stored_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                btc = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 3)
                eth = await SyntheticFixtureAdapter().get_bars("ETHUSD", "1h", 2)
                store_batch(btc)
                store_batch(eth)
                overview = get_market_overview()
                self.assertEqual(overview["status"], "stored_data_overview")
                self.assertEqual(overview["instrument_interval_count"], 2)
                btc_row = next(item for item in overview["coverage"] if item["symbol"] == "BTCUSD")
                self.assertEqual(btc_row["observation_count"], 3)
                self.assertEqual(btc_row["statuses"], ["synthetic"])
                self.assertIn("not a live quote", overview["data_note"])


    async def test_stored_return_heatmap_uses_latest_two_distinct_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 5)
                store_batch(batch)
                heatmap = get_stored_return_heatmap("1d")
                self.assertEqual(heatmap["status"], "stored_return_heatmap")
                self.assertEqual(heatmap["instrument_count"], 1)
                cell = heatmap["cells"][0]
                self.assertEqual(cell["symbol"], "BTCUSD")
                self.assertEqual(cell["status"], "calculated")
                self.assertAlmostEqual(cell["change_pct"], (105.0 - 103.5) / 103.5 * 100, places=6)
                self.assertEqual(cell["sources"], ["synthetic-fixture"])
                self.assertIn("not live data", heatmap["data_note"])

    async def test_stored_return_heatmap_deduplicates_sources_and_flags_short_history(self):
        from datetime import datetime, timedelta, timezone
        from app.market_data import DataStatus, MarketDataBatch, OHLCVBar

        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                retrieved = datetime(2026, 2, 1, tzinfo=timezone.utc)
                bars_a = [
                    OHLCVBar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), open=100, high=101, low=99, close=100, volume=10),
                    OHLCVBar(timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), open=100, high=111, low=99, close=110, volume=12),
                ]
                first = MarketDataBatch(symbol="AAA", interval="1d", status=DataStatus.HISTORICAL,
                    source="source-a", retrieved_at=retrieved, bars=bars_a)
                second = MarketDataBatch(symbol="AAA", interval="1d", status=DataStatus.HISTORICAL,
                    source="source-b", retrieved_at=retrieved + timedelta(hours=1), bars=[
                        bars_a[1].model_copy(update={"close": 105, "open": 100, "high": 106})
                    ])
                one_bar = MarketDataBatch(symbol="BBB", interval="1d", status=DataStatus.SYNTHETIC,
                    source="fixture", retrieved_at=retrieved, bars=[bars_a[0].model_copy()])
                store_batch(first)
                store_batch(second)
                store_batch(one_bar)

                heatmap = get_stored_return_heatmap("1d")
                aaa = next(cell for cell in heatmap["cells"] if cell["symbol"] == "AAA")
                bbb = next(cell for cell in heatmap["cells"] if cell["symbol"] == "BBB")
                self.assertAlmostEqual(aaa["change_pct"], 5.0)
                self.assertEqual(aaa["sources"], ["source-a", "source-b"])
                self.assertEqual(bbb["status"], "insufficient_history")
                self.assertIsNone(bbb["change_pct"])
                self.assertEqual(heatmap["insufficient_history_count"], 1)

    async def test_stored_return_heatmap_respects_limit_and_empty_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                empty = get_stored_return_heatmap("1d")
                self.assertEqual(empty["cells"], [])
                batch_a = await SyntheticFixtureAdapter().get_bars("AAA", "1d", 5)
                batch_b = await SyntheticFixtureAdapter().get_bars("BBB", "1d", 5)
                store_batch(batch_a)
                store_batch(batch_b)
                limited = get_stored_return_heatmap("1d", limit=1)
                self.assertEqual(limited["instrument_count"], 1)
                self.assertEqual(limited["available_instrument_count"], 2)

    def test_bar_reads_and_heatmap_preserve_microsecond_distinctions(self):
        from datetime import timedelta

        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                base = datetime(2026, 3, 1, tzinfo=timezone.utc)
                batch = MarketDataBatch(
                    symbol="MICRO", interval="1d", status=DataStatus.HISTORICAL,
                    source="microsecond-fixture", retrieved_at=base + timedelta(days=1),
                    bars=[
                        OHLCVBar(timestamp=base, open=100, high=101, low=99, close=100, volume=10),
                        OHLCVBar(timestamp=base + timedelta(microseconds=1), open=100, high=102, low=99, close=101, volume=11),
                    ],
                )
                store_batch(batch)

                latest_only = get_bars("MICRO", "1d", limit=1)
                self.assertEqual(latest_only["count"], 1)
                self.assertEqual(
                    latest_only["bars"][0]["timestamp"],
                    (base + timedelta(microseconds=1)).isoformat(),
                )
                heatmap = get_stored_return_heatmap("1d")
                self.assertEqual(heatmap["cells"][0]["status"], "calculated")
                self.assertAlmostEqual(heatmap["cells"][0]["change_pct"], 1.0)

    def test_unknown_symbol_returns_empty_history(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                result = get_bars("UNKNOWN", "1d")
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["bars"], [])


if __name__ == "__main__":
    unittest.main()
