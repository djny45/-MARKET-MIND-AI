import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

from app.main import SnapshotForecastEvaluationRequest, evaluate_snapshot_research_forecasts
from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.market_store import store_batch


class SnapshotForecastEvaluationApiTests(unittest.TestCase):
    def _create_snapshot(self, directory):
        database = os.path.join(directory, "snapshot-forecast.sqlite")
        patcher = patch.dict(os.environ, {"MARKET_MIND_DB": database})
        patcher.start()
        self.addCleanup(patcher.stop)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bars = [
            OHLCVBar(
                timestamp=now + timedelta(days=index),
                open=100 + index, high=102 + index, low=99 + index,
                close=100 + index, volume=1000 + index,
            )
            for index in range(40)
        ]
        store_batch(MarketDataBatch(
            symbol="BTCUSD", interval="1d", status=DataStatus.HISTORICAL,
            source="snapshot-feed", retrieved_at=now, bars=bars,
        ))
        from app.main import create_research_evaluation_snapshot
        return create_research_evaluation_snapshot({
            "symbol": "BTCUSD", "interval": "1d", "limit": 40,
            "train_ratio": 0.6, "validation_ratio": 0.2,
            "embargo_bars": 1, "revision_policy": "annotate",
        })

    def _records(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = []
        for origin_index, target_index in [(33, 34), (34, 35), (35, 36)]:
            origin = base + timedelta(days=origin_index)
            target = base + timedelta(days=target_index)
            rows.append({
                "source": "snapshot-feed",
                "partition": "holdout",
                "forecast_created_at": origin.isoformat(),
                "origin_timestamp": origin.isoformat(),
                "target_timestamp": target.isoformat(),
                "predicted_return": 0.03,
                "actual_return": 999,
                "source_refs": ["forecast-log:fixture"],
            })
        return rows

    def test_evaluation_uses_realized_returns_from_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = self._create_snapshot(directory)
            result = evaluate_snapshot_research_forecasts(
                SnapshotForecastEvaluationRequest(
                    snapshot_id=snapshot["snapshot_id"], records=self._records()
                )
            )
            self.assertEqual(result["mode"], "snapshot_backed_holdout_forecast_evaluation")
            self.assertEqual(result["snapshot"]["snapshot_id"], snapshot["snapshot_id"])
            self.assertEqual(result["actual_return_method"],
                             "close_to_close_simple_return_from_verified_snapshot_bars")
            self.assertAlmostEqual(result["metrics"]["mae"], sum(abs(0.03 - 3 / value) for value in (133, 134, 135)) / 3)
            self.assertNotEqual(result["metrics"]["mae"], 0.0)

    def test_target_outside_holdout_partition_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = self._create_snapshot(directory)
            rows = self._records()
            rows[0]["origin_timestamp"] = "2026-01-25T00:00:00+00:00"
            rows[0]["forecast_created_at"] = "2026-01-25T00:00:00+00:00"
            rows[0]["target_timestamp"] = "2026-01-26T00:00:00+00:00"
            with self.assertRaises(HTTPException) as error:
                evaluate_snapshot_research_forecasts(
                    SnapshotForecastEvaluationRequest(
                        snapshot_id=snapshot["snapshot_id"], records=rows
                    )
                )
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("outside the source holdout partition", error.exception.detail)

    def test_origin_outside_holdout_partition_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = self._create_snapshot(directory)
            rows = self._records()
            rows[0]["origin_timestamp"] = "2026-02-02T00:00:00+00:00"
            rows[0]["forecast_created_at"] = "2026-02-02T00:00:00+00:00"
            rows[0]["target_timestamp"] = "2026-02-04T00:00:00+00:00"
            with self.assertRaises(HTTPException) as error:
                evaluate_snapshot_research_forecasts(
                    SnapshotForecastEvaluationRequest(
                        snapshot_id=snapshot["snapshot_id"], records=rows
                    )
                )
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("origin_timestamp is outside the source holdout partition", error.exception.detail)

    def test_unknown_snapshot_is_not_evaluated(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "missing.sqlite")}):
                with self.assertRaises(HTTPException) as error:
                    evaluate_snapshot_research_forecasts(
                        SnapshotForecastEvaluationRequest(
                            snapshot_id="0" * 64, records=self._records()
                        )
                    )
                self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
