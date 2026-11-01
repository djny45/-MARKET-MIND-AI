import os
import tempfile
import unittest
from unittest.mock import patch

from app.market_data import SyntheticFixtureAdapter
from app.market_store import (get_audit_events, get_bar_revisions, get_bars, get_data_lineage, get_revised_bar_keys, get_market_overview, store_batch, create_evaluation_manifest_snapshot, get_evaluation_manifest_snapshot, list_evaluation_manifest_snapshots, verify_evaluation_manifest_snapshot)


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
                self.assertEqual(version, 3)

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


    async def test_changed_existing_bar_creates_append_only_revision_record(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 3)
                store_batch(batch)
                changed_bars = [
                    bar.model_copy(update={"close": bar.close + 2.5})
                    if index == 1 else bar
                    for index, bar in enumerate(batch.bars)
                ]
                revised_batch = batch.model_copy(update={"bars": changed_bars})
                result = store_batch(revised_batch)
                self.assertEqual(result["revision_count"], 1)
                revisions = get_bar_revisions("BTCUSD", "1d", "synthetic-fixture")
                self.assertEqual(revisions["count"], 1)
                revision = revisions["revisions"][0]
                self.assertNotEqual(revision["previous_sha256"], revision["revised_sha256"])
                self.assertNotEqual(
                    revision["previous_values"]["close"],
                    revision["revised_values"]["close"],
                )
                self.assertEqual(
                    get_bars("BTCUSD", "1d")["bars"][1]["close"],
                    batch.bars[1].close + 2.5,
                )

    async def test_retrieval_timestamp_only_update_is_not_a_content_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("ETHUSD", "1d", 2)
                store_batch(batch)
                later = batch.model_copy(update={
                    "retrieved_at": batch.retrieved_at.replace(year=batch.retrieved_at.year + 1)
                })
                result = store_batch(later)
                self.assertEqual(result["revision_count"], 0)
                self.assertEqual(get_bar_revisions("ETHUSD", "1d")["count"], 0)

    async def test_revision_history_filters_by_symbol_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 2)
                store_batch(batch)
                changed = batch.model_copy(update={
                    "bars": [batch.bars[0].model_copy(update={"volume": batch.bars[0].volume + 1}), batch.bars[1]]
                })
                store_batch(changed)
                self.assertEqual(get_bar_revisions(symbol="ETHUSD")["count"], 0)
                self.assertEqual(get_bar_revisions(source="other-provider")["count"], 0)
                self.assertEqual(get_bar_revisions(limit=1)["count"], 1)


    def test_populated_version_one_database_migrates_without_losing_bars(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "legacy.sqlite")
            with sqlite3.connect(database) as connection:
                connection.execute("""
                    CREATE TABLE schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                """)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)",
                    ("2026-01-01T00:00:00+00:00",),
                )
                connection.execute("""
                    CREATE TABLE market_bars (
                        symbol TEXT NOT NULL, interval TEXT NOT NULL,
                        timestamp TEXT NOT NULL, open REAL NOT NULL,
                        high REAL NOT NULL, low REAL NOT NULL,
                        close REAL NOT NULL, volume REAL NOT NULL,
                        status TEXT NOT NULL, source TEXT NOT NULL,
                        retrieved_at TEXT NOT NULL,
                        PRIMARY KEY (symbol, interval, timestamp, source)
                    )
                """)
                connection.execute("""
                    INSERT INTO market_bars VALUES (
                        'BTCUSD', '1d', '2026-01-01T00:00:00+00:00',
                        10, 12, 9, 11, 100, 'historical', 'legacy-feed',
                        '2026-01-02T00:00:00+00:00'
                    )
                """)
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}):
                revisions = get_bar_revisions("BTCUSD", "1d", "legacy-feed")
                saved = get_bars("BTCUSD", "1d")
            self.assertEqual(revisions["count"], 0)
            self.assertEqual(saved["count"], 1)
            self.assertEqual(saved["bars"][0]["close"], 11)
            with sqlite3.connect(database) as connection:
                version = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]
                revision_table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_bar_revisions'"
                ).fetchone()
            self.assertEqual(version, 3)
            self.assertIsNotNone(revision_table)


    async def test_revisioned_bar_keys_only_include_currently_stored_revised_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 3)
                store_batch(batch)
                revised_batch = batch.model_copy(update={
                    "bars": [
                        bar.model_copy(update={"volume": bar.volume + 5})
                        if index == 1 else bar
                        for index, bar in enumerate(batch.bars)
                    ]
                })
                store_batch(revised_batch)
                keys = get_revised_bar_keys("BTCUSD", "1d")
                self.assertEqual(keys["count"], 1)
                self.assertEqual(keys["keys"][0]["source"], "synthetic-fixture")
                self.assertEqual(
                    keys["keys"][0]["timestamp"],
                    batch.bars[1].timestamp.isoformat(),
                )
                self.assertEqual(get_revised_bar_keys("ETHUSD", "1d")["count"], 0)

    def test_evaluation_manifest_snapshot_round_trip_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                manifest = {"symbol": "TEST", "interval": "1h", "ready_source_count": 1}
                parameters = {"limit": 100, "revision_policy": "annotate"}
                dataset = [{"timestamp": "2026-01-01T00:00:00+00:00", "close": 10.5, "source": "fixture"}]
                first = create_evaluation_manifest_snapshot(manifest, parameters, dataset)
                second = create_evaluation_manifest_snapshot(manifest, parameters, dataset)
                self.assertEqual(first["snapshot_id"], second["snapshot_id"])
                self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
                saved = get_evaluation_manifest_snapshot(first["snapshot_id"])
                self.assertEqual(saved["manifest"], manifest)
                self.assertEqual(saved["request_parameters"], parameters)
                self.assertEqual(saved["dataset_bars"], dataset)
                self.assertEqual(saved["dataset_sha256"], first["dataset_sha256"])
                listed = list_evaluation_manifest_snapshots("test")
                self.assertEqual(listed["count"], 1)
                self.assertEqual(listed["snapshots"][0]["snapshot_id"], first["snapshot_id"])

    def test_evaluation_manifest_snapshot_integrity_verification_detects_payload_change(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "test.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}):
                manifest = {"symbol": "TEST", "interval": "1h", "ready_source_count": 1}
                snapshot = create_evaluation_manifest_snapshot(manifest, {"limit": 10})
                verified = verify_evaluation_manifest_snapshot(snapshot["snapshot_id"])
                self.assertEqual(verified["status"], "verified")
                self.assertTrue(verified["manifest_digest_valid"])
                self.assertTrue(verified["dataset_digest_valid"])
                with sqlite3.connect(database) as connection:
                    connection.execute(
                        "UPDATE evaluation_manifest_snapshots SET manifest_json=? WHERE snapshot_id=?",
                        ('{"interval":"1h","ready_source_count":99,"symbol":"TEST"}', snapshot["snapshot_id"]),
                    )
                tampered = verify_evaluation_manifest_snapshot(snapshot["snapshot_id"])
                self.assertEqual(tampered["status"], "integrity_mismatch")
                self.assertFalse(tampered["manifest_digest_valid"])
                self.assertTrue(tampered["dataset_digest_valid"])
                self.assertFalse(tampered["snapshot_id_valid"])

    def test_unknown_symbol_returns_empty_history(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                result = get_bars("UNKNOWN", "1d")
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["bars"], [])


if __name__ == "__main__":
    unittest.main()
