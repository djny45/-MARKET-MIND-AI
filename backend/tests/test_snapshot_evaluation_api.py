import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

from app.main import create_research_evaluation_snapshot, evaluate_snapshot_holdout_forecasts
from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.market_store import store_batch


class SnapshotBoundEvaluationApiTests(unittest.TestCase):
    def _create_snapshot(self, database):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bars = [OHLCVBar(
            timestamp=now + timedelta(days=index),
            open=100 + index, high=102 + index, low=99 + index,
            close=101 + index, volume=1000 + index,
        ) for index in range(40)]
        store_batch(MarketDataBatch(
            symbol="BTCUSD", interval="1d", status=DataStatus.HISTORICAL,
            source="snapshot-feed", retrieved_at=now, bars=bars,
        ))
        snapshot = create_research_evaluation_snapshot({
            "symbol": "BTCUSD", "interval": "1d", "limit": 40,
            "train_ratio": 0.6, "validation_ratio": 0.2, "embargo_bars": 1,
        })
        return snapshot, now

    def _records(self, now):
        return [
            {
                "partition": "holdout", "source": "snapshot-feed",
                "forecast_created_at": (now + timedelta(days=33)).isoformat(),
                "origin_timestamp": (now + timedelta(days=33)).isoformat(),
                "target_timestamp": (now + timedelta(days=34 + index)).isoformat(),
                "predicted_return": prediction, "actual_return": actual,
                "source_refs": [f"snapshot-feed:bar:{index}"],
            }
            for index, (prediction, actual) in enumerate(
                [(0.02, 0.01), (-0.01, -0.02), (0.0, 0.01)]
            )
        ]

    def test_snapshot_bound_holdout_evaluation_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "eval.sqlite")}):
                snapshot, now = self._create_snapshot(os.environ["MARKET_MIND_DB"])
                result = evaluate_snapshot_holdout_forecasts(
                    snapshot["snapshot_id"], {"records": self._records(now)}
                )
                self.assertEqual(result["partition"], "holdout")
                self.assertEqual(result["snapshot"]["snapshot_id"], snapshot["snapshot_id"])
                self.assertEqual(result["snapshot"]["integrity_status"], "verified")
                self.assertEqual(result["observation_count"], 3)

    def test_snapshot_bound_evaluation_rejects_out_of_holdout_target(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "eval.sqlite")}):
                snapshot, now = self._create_snapshot(os.environ["MARKET_MIND_DB"])
                rows = self._records(now)
                rows[0]["target_timestamp"] = (now + timedelta(days=20)).isoformat()
                with self.assertRaises(HTTPException) as error:
                    evaluate_snapshot_holdout_forecasts(snapshot["snapshot_id"], {"records": rows})
                self.assertEqual(error.exception.status_code, 400)
                self.assertIn("inside the snapshot holdout range", error.exception.detail)

    def test_snapshot_bound_evaluation_rejects_unknown_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "eval.sqlite")}):
                snapshot, now = self._create_snapshot(os.environ["MARKET_MIND_DB"])
                rows = self._records(now)
                rows[0]["source"] = "unrelated-feed"
                with self.assertRaises(HTTPException) as error:
                    evaluate_snapshot_holdout_forecasts(snapshot["snapshot_id"], {"records": rows})
                self.assertEqual(error.exception.status_code, 400)
                self.assertIn("ready snapshot source", error.exception.detail)

    def test_snapshot_bound_evaluation_rejects_corrupted_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "eval.sqlite")
            with patch.dict(os.environ, {"MARKET_MIND_DB": database}):
                snapshot, now = self._create_snapshot(database)
                with sqlite3.connect(database) as connection:
                    connection.execute(
                        "UPDATE evaluation_manifest_snapshots SET dataset_json='[]' WHERE snapshot_id=?",
                        (snapshot["snapshot_id"],),
                    )
                with self.assertRaises(HTTPException) as error:
                    evaluate_snapshot_holdout_forecasts(snapshot["snapshot_id"], {"records": self._records(now)})
                self.assertEqual(error.exception.status_code, 400)
                self.assertIn("integrity verification must pass", error.exception.detail)

    def test_snapshot_bound_evaluation_rejects_unknown_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "eval.sqlite")}):
                with self.assertRaises(HTTPException) as error:
                    evaluate_snapshot_holdout_forecasts("0" * 64, {"records": []})
                self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
