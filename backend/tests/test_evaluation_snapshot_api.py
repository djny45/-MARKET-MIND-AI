import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import (
    create_research_evaluation_snapshot,
    get_research_evaluation_snapshot,
    list_research_evaluation_snapshots,
)
from app.market_data import SyntheticFixtureAdapter
from app.market_store import store_batch


class EvaluationSnapshotApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_get_and_list_snapshot_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "snapshots.sqlite")}):
                batch = await SyntheticFixtureAdapter().get_bars("BTCUSD", "1d", 40)
                store_batch(batch)
                saved = create_research_evaluation_snapshot({
                    "symbol": "BTCUSD", "interval": "1d", "limit": 40,
                    "train_ratio": 0.6, "validation_ratio": 0.2,
                    "embargo_bars": 1, "revision_policy": "annotate",
                })
                self.assertEqual(saved["symbol"], "BTCUSD")
                self.assertEqual(len(saved["snapshot_id"]), 64)
                self.assertEqual(len(saved["manifest_sha256"]), 64)
                restored = get_research_evaluation_snapshot(saved["snapshot_id"])
                self.assertEqual(restored["manifest"], saved["manifest"])
                self.assertEqual(restored["request_parameters"], saved["request_parameters"])
                listed = list_research_evaluation_snapshots("BTCUSD", 10)
                self.assertEqual(listed["count"], 1)
                self.assertEqual(listed["snapshots"][0]["snapshot_id"], saved["snapshot_id"])

    async def test_create_snapshot_rejects_invalid_request(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "snapshots.sqlite")}):
                with self.assertRaises(HTTPException) as error:
                    create_research_evaluation_snapshot({"symbol": "", "interval": "1d"})
                self.assertEqual(error.exception.status_code, 400)

    async def test_snapshot_lookup_validates_identifier_and_missing_record(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "snapshots.sqlite")}):
                with self.assertRaises(HTTPException) as invalid:
                    get_research_evaluation_snapshot("not-a-digest")
                self.assertEqual(invalid.exception.status_code, 400)
                with self.assertRaises(HTTPException) as missing:
                    get_research_evaluation_snapshot("0" * 64)
                self.assertEqual(missing.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
