import os
import tempfile
import unittest
from unittest.mock import patch

from app.csv_import import parse_historical_csv
from app.market_store import get_bars, store_batch


CSV = """timestamp,open,high,low,close,volume
2026-01-02T00:00:00Z,11,13,10,12,150
2026-01-01T00:00:00+00:00,10,12,9,11,100
"""


class HistoricalCSVImportTests(unittest.TestCase):
    def test_parses_historical_csv_and_retains_source(self):
        batch = parse_historical_csv(CSV, " btcusd ", "1d", "user-upload")
        self.assertEqual(batch.symbol, "BTCUSD")
        self.assertEqual(batch.status.value, "historical")
        self.assertEqual(batch.source, "user-upload")
        self.assertEqual(len(batch.bars), 2)
        self.assertTrue(batch.warnings)

    def test_rejects_missing_columns(self):
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            parse_historical_csv("timestamp,close\n2026-01-01T00:00:00Z,10", "BTC", "1d", "upload")

    def test_rejects_timezone_naive_timestamp(self):
        csv_text = "timestamp,open,high,low,close,volume\n2026-01-01,10,12,9,11,100"
        with self.assertRaisesRegex(ValueError, "Invalid CSV row"):
            parse_historical_csv(csv_text, "BTC", "1d", "upload")

    def test_rejects_duplicate_timestamps(self):
        duplicate = CSV + "2026-01-01T00:00:00Z,10,12,9,11,100\n"
        with self.assertRaisesRegex(ValueError, "duplicate bar timestamps"):
            parse_historical_csv(duplicate, "BTC", "1d", "upload")

    def test_rejects_invalid_ohlc_row(self):
        bad = "timestamp,open,high,low,close,volume\n2026-01-01T00:00:00Z,10,9,8,11,100"
        with self.assertRaisesRegex(ValueError, "Invalid CSV row"):
            parse_historical_csv(bad, "BTC", "1d", "upload")

    def test_rejects_duplicate_normalized_headers(self):
        duplicate = "timestamp,open,high,low,close,volume, OPEN\\n2026-01-01T00:00:00Z,10,12,9,11,100,10"
        with self.assertRaisesRegex(ValueError, "duplicate column names"):
            parse_historical_csv(duplicate, "BTC", "1d", "upload")

    def test_rejects_row_with_extra_or_missing_columns(self):
        malformed = "timestamp,open,high,low,close,volume\\n2026-01-01T00:00:00Z,10,12,9,11,100,extra"
        with self.assertRaisesRegex(ValueError, "column count does not match"):
            parse_historical_csv(malformed, "BTC", "1d", "upload")

    def test_rejects_non_finite_numeric_values(self):
        malformed = "timestamp,open,high,low,close,volume\\n2026-01-01T00:00:00Z,10,12,9,11,nan"
        with self.assertRaisesRegex(ValueError, "finite numbers"):
            parse_historical_csv(malformed, "BTC", "1d", "upload")

    def test_imported_batch_stores_in_chronological_order(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(directory, "test.sqlite")}):
                batch = parse_historical_csv(CSV, "BTC", "1d", "user-upload")
                result = store_batch(batch)
                history = get_bars("BTC", "1d")
                self.assertEqual(result["stored"], 2)
                self.assertEqual(history["bars"][0]["close"], 11)
                self.assertEqual(history["bars"][1]["close"], 12)


if __name__ == "__main__":
    unittest.main()
