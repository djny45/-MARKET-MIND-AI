import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

from app.main import research_source_indicators
from app.market_data import DataStatus, MarketDataBatch, OHLCVBar
from app.market_store import store_batch


class SourceIndicatorApiTests(unittest.TestCase):
    def _batch(self, source, now, offset=0.0):
        bars = []
        for index in range(40):
            close = 100 + index * 0.35 + (index % 4) * 0.15 + offset
            bars.append(OHLCVBar(
                timestamp=now + timedelta(hours=index),
                open=close - 0.1, high=close + 0.5, low=close - 0.5,
                close=close, volume=1000 + index,
            ))
        return MarketDataBatch(
            symbol="BTCUSD", interval="1h", status=DataStatus.HISTORICAL,
            source=source, retrieved_at=now + timedelta(days=2), bars=bars,
        )

    def test_source_indicator_endpoint_applies_revision_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "source-indicators.sqlite")}):
                now = datetime(2026, 1, 1, tzinfo=timezone.utc)
                alpha = self._batch("alpha-feed", now)
                beta = self._batch("beta-feed", now, offset=0.2)
                store_batch(alpha)
                store_batch(beta)
                changed = list(alpha.bars)
                changed[10] = changed[10].model_copy(update={"close": changed[10].close + 0.05})
                store_batch(alpha.model_copy(update={"bars": changed}))

                annotated = research_source_indicators("BTCUSD", "1h", 100, "annotate")
                alpha_report = annotated["source_reports"]["alpha-feed"]
                self.assertEqual(alpha_report["revised_observation_count"], 1)
                self.assertTrue(alpha_report["revision_review_required"])
                self.assertEqual(annotated["evaluated_source_count"], 2)

                excluded = research_source_indicators("BTCUSD", "1h", 100, "exclude_revised")
                alpha_report = excluded["source_reports"]["alpha-feed"]
                self.assertEqual(alpha_report["excluded_revised_observation_count"], 1)
                self.assertEqual(alpha_report["valid_observation_count"], 39)

                blocked = research_source_indicators("BTCUSD", "1h", 100, "block_revised")
                self.assertEqual(
                    blocked["source_reports"]["alpha-feed"]["status"],
                    "blocked_revised_observations",
                )
                self.assertEqual(blocked["evaluated_source_count"], 1)

    def test_source_indicator_endpoint_rejects_unknown_revision_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "source-indicators.sqlite")}):
                with self.assertRaises(HTTPException) as error:
                    research_source_indicators("BTCUSD", "1h", 100, "ignore")
                self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
