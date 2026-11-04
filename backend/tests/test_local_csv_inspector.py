"""Tests for the local CSV inspector example."""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from examples.local_csv_inspector import inspect_csv


class LocalCsvInspectorTests(unittest.TestCase):
    def test_reports_headers_and_row_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            path.write_text("time,close\n2025-01-01,10\n2025-01-02,11\n", encoding="utf-8")
            result = inspect_csv(path)
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["columns"], ["time", "close"])

    def test_rejects_headerless_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "header row"):
                inspect_csv(path)


if __name__ == "__main__":
    unittest.main()
