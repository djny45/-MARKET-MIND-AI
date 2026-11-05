"""Tests for the local-only OHLCV CSV loader."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

available = all(importlib.util.find_spec(name) is not None for name in ("pandas", "numpy"))


@unittest.skipUnless(available, "optional pandas/numpy research dependencies not installed")
class OfflineDatasetTests(unittest.TestCase):
    def write_csv(self, text):
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        temp.write(text)
        temp.close()
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return temp.name

    def test_loads_and_sorts_timestamps(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv(
            "Timestamp,Open,High,Low,Close,Volume\n"
            "2024-01-02T00:00:00Z,2,3,1,2.5,10\n"
            "2024-01-01T00:00:00Z,1,2,0.5,1.5,5\n"
        )
        frame = load_ohlcv_csv(path, timestamp_column="Timestamp")
        self.assertEqual(frame["close"].tolist(), [1.5, 2.5])
        self.assertEqual(str(frame["timestamp"].dt.tz), "UTC")

    def test_blank_column_name_rejected_after_normalization(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv("open,high,low,close,   \n1,2,0.5,1.5,7\n")
        with self.assertRaisesRegex(ValueError, "empty column name"):
            load_ohlcv_csv(path)

    def test_duplicate_columns_rejected_after_normalization(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv("open, high,high,low,close\n1,2,2,0.5,1.5\n")
        with self.assertRaisesRegex(ValueError, "duplicate columns"):
            load_ohlcv_csv(path)

    def test_missing_ohlc_column_rejected(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv("open,high,close\n1,2,1.5\n")
        with self.assertRaisesRegex(ValueError, "Missing required OHLC"):
            load_ohlcv_csv(path)

    def test_invalid_ohlc_rejected(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv("open,high,low,close\n1,0,0.5,1.2\n")
        with self.assertRaisesRegex(ValueError, "high is below"):
            load_ohlcv_csv(path)

    def test_duplicate_timestamps_rejected(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv(
            "time,open,high,low,close\n"
            "2024-01-01T00:00:00Z,1,2,0.5,1.5\n"
            "2024-01-01T00:00:00Z,1,2,0.5,1.5\n"
        )
        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            load_ohlcv_csv(path, timestamp_column="time")

    def test_numeric_epoch_timestamps_rejected_as_ambiguous(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv(
            "timestamp,open,high,low,close\n"
            "1704067200,1,2,0.5,1.5\n"
            "1704153600,1,2,0.5,1.5\n"
        )
        with self.assertRaisesRegex(ValueError, "Numeric timestamps are ambiguous"):
            load_ohlcv_csv(path, timestamp_column="timestamp")

    def test_missing_timestamp_rejected(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv(
            "timestamp,open,high,low,close\n"
            "2024-01-01T00:00:00Z,1,2,0.5,1.5\n"
            ",1,2,0.5,1.5\n"
        )
        with self.assertRaisesRegex(ValueError, "Missing timestamps"):
            load_ohlcv_csv(path, timestamp_column="timestamp")

    def test_timestamp_cannot_overwrite_ohlcv_column(self):
        from app.offline_dataset import load_ohlcv_csv
        path = self.write_csv("open,high,low,close\n1,2,0.5,1.5\n")
        with self.assertRaisesRegex(ValueError, "cannot be an OHLCV field"):
            load_ohlcv_csv(path, timestamp_column="open")


if __name__ == "__main__":
    unittest.main()
