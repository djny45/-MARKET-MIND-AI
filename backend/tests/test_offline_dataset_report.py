"""Tests for the offline OHLCV dataset report."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

available = all(importlib.util.find_spec(name) is not None for name in ("pandas", "numpy"))


@unittest.skipUnless(available, "optional pandas/numpy research dependencies not installed")
class OfflineDatasetReportTests(unittest.TestCase):
    def write_csv(self, content):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        handle.write(content)
        handle.close()
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return handle.name

    def test_report_contains_basic_quality_and_summary(self):
        from examples.offline_dataset_report import build_report
        path = self.write_csv(
            "timestamp,open,high,low,close,volume\n"
            "2024-01-02,2,3,1,2.5,10\n"
            "2024-01-01,1,2,0.5,1.5,5\n"
        )
        report = build_report(path, timestamp_column="timestamp")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["numeric_summary"]["close"]["min"], 1.5)
        self.assertEqual(report["numeric_summary"]["volume"]["max"], 10.0)
        self.assertTrue(report["quality_checks"]["unique_timestamps"])
        self.assertTrue(report["quality_checks"]["chronological_after_sort"])
        self.assertEqual(report["time_range_utc"]["start"], "2024-01-01T00:00:00+00:00")

    def test_invalid_dataset_is_rejected(self):
        from examples.offline_dataset_report import build_report
        path = self.write_csv("open,high,low,close\n1,0,0.5,1.2\n")
        with self.assertRaisesRegex(ValueError, "high is below"):
            build_report(path)


if __name__ == "__main__":
    unittest.main()
