"""Unit tests for the offline indicator JSON report exporter."""
import unittest
from unittest.mock import patch

from examples import offline_indicator_report as exporter


class FakeDataset:
    columns = ["timestamp", "open", "high", "low", "close"]

    def __getitem__(self, key):
        if key == "timestamp":
            return ["2024-01-01T00:00:00", None]
        raise KeyError(key)


class OfflineIndicatorReportTests(unittest.TestCase):
    @patch.object(exporter, "run_offline_research")
    def test_build_report_serializes_nan_as_null_and_counts_values(self, run_pipeline):
        run_pipeline.return_value = {
            "row_count": 3,
            "columns": ["open", "high", "low", "close"],
            "dataset": FakeDataset(),
            "indicators": {"ta_lib": {
                "rsi": [float("nan"), 42.5, float("inf")],
                "empty": [float("nan"), float("nan")],
            }},
        }

        report = exporter.build_report("sample.csv", include_ta_lib=True)

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["row_count"], 3)
        self.assertEqual(report["indicator_source"], "TA-Lib")
        self.assertEqual(report["indicators"]["rsi"]["values"], [None, 42.5, None])
        self.assertEqual(report["indicators"]["rsi"]["valid_count"], 1)
        self.assertEqual(report["indicators"]["rsi"]["null_count"], 2)
        self.assertEqual(report["indicators"]["rsi"]["latest_valid"], 42.5)
        self.assertEqual(report["indicators"]["empty"]["latest_valid"], None)

    @patch.object(exporter, "run_offline_research")
    def test_timestamp_column_is_included_when_requested(self, run_pipeline):
        run_pipeline.return_value = {
            "row_count": 2,
            "columns": FakeDataset.columns,
            "dataset": FakeDataset(),
            "indicators": {},
        }

        report = exporter.build_report("sample.csv", timestamp_column="timestamp")

        self.assertEqual(report["timestamps"], [
            "2024-01-01T00:00:00", None
        ])
        run_pipeline.assert_called_once_with(
            "sample.csv", timestamp_column="timestamp", include_ta_lib=False
        )

    @patch.object(exporter, "run_offline_research")
    def test_timestamp_column_normalizes_case_and_whitespace(self, run_pipeline):
        run_pipeline.return_value = {
            "row_count": 2,
            "columns": FakeDataset.columns,
            "dataset": FakeDataset(),
            "indicators": {},
        }

        report = exporter.build_report("sample.csv", timestamp_column=" Timestamp ")

        self.assertEqual(report["timestamp_column"], "timestamp")
        self.assertEqual(report["timestamps"], [
            "2024-01-01T00:00:00", None
        ])
        run_pipeline.assert_called_once_with(
            "sample.csv", timestamp_column=" Timestamp ", include_ta_lib=False
        )

    @patch.object(exporter, "run_offline_research")
    def test_report_without_talib_has_empty_indicator_map(self, run_pipeline):
        run_pipeline.return_value = {
            "row_count": 1,
            "columns": ["open", "high", "low", "close"],
            "dataset": FakeDataset(),
            "indicators": {},
        }

        report = exporter.build_report("sample.csv")

        self.assertEqual(report["indicator_source"], "none")
        self.assertEqual(report["indicators"], {})
        self.assertTrue(report["limitations"])


if __name__ == "__main__":
    unittest.main()
