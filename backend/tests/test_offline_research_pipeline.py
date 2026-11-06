"""Tests for offline research orchestration."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

available = all(importlib.util.find_spec(name) is not None for name in ("pandas", "numpy"))


@unittest.skipUnless(available, "optional pandas/numpy research dependencies not installed")
class OfflineResearchPipelineTests(unittest.TestCase):
    def write_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as file:
            file.write("timestamp,open,high,low,close\n")
            file.write("2024-01-01T00:00:00Z,10,12,9,11\n")
            file.write("2024-01-02T00:00:00Z,11,13,10,12\n")
            path = file.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        return path

    def test_pipeline_loads_dataset_without_optional_indicators(self):
        from app.offline_research_pipeline import run_offline_research
        self._last_csv_path = self.write_csv()
        result = run_offline_research(self._last_csv_path, timestamp_column="timestamp")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["source_path"], str(Path(self._last_csv_path).resolve()))
        self.assertIn("dataset", result)
        self.assertEqual(result["indicators"], {})

    def test_pipeline_records_sha256_of_exact_source_file(self):
        import hashlib
        from app.offline_research_pipeline import run_offline_research
        path = self.write_csv()
        result = run_offline_research(path, timestamp_column="timestamp")
        expected = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        self.assertEqual(result["source_sha256"], expected)
        self.assertEqual(len(result["source_sha256"]), 64)


    def test_offline_csv_export_carries_source_hash_into_evidence_scope(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        import hashlib
        path = self.write_csv()
        result = run_offline_research(path, timestamp_column="timestamp")
        bundle = build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")
        self.assertEqual(bundle["scope"]["source_sha256"], hashlib.sha256(
            Path(path).read_bytes()).hexdigest())
        self.assertEqual(bundle["scope"]["source"], str(Path(path).resolve()))
        self.assertEqual(bundle["scope"]["observation_count"], 2)
        self.assertEqual(bundle["observations"][0]["timestamp"], "2024-01-01T00:00:00+00:00")

    def test_offline_export_requires_recognized_timestamp_column(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        path = self.write_csv()
        result = run_offline_research(path, timestamp_column="timestamp")
        result["dataset"] = result["dataset"].drop(columns=["timestamp"])
        with self.assertRaisesRegex(ValueError, "exactly one recognized timestamp"):
            build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")

    def test_offline_export_uses_custom_timestamp_column(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as file:
            file.write("time_utc,open,high,low,close\\n")
            file.write("2024-01-01T00:00:00Z,10,12,9,11\\n")
            file.write("2024-01-02T00:00:00Z,11,13,10,12\\n")
            path = file.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        result = run_offline_research(path, timestamp_column="time_utc")
        bundle = build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")
        self.assertEqual(bundle["scope"]["observation_count"], 2)
        self.assertEqual(bundle["observations"][0]["timestamp"], "2024-01-01T00:00:00+00:00")

    def test_indicator_pipeline_requires_timestamp_column(self):
        from app.offline_research_pipeline import run_offline_research
        with self.assertRaisesRegex(ValueError, "timestamp_column is required"):
            run_offline_research(self.write_csv(), include_smc=True)


if __name__ == "__main__":
    unittest.main()
