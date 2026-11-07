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

    def test_pipeline_hashes_and_parses_one_snapshot_if_source_changes_during_load(self):
        import hashlib
        from unittest.mock import patch
        from app.offline_research_pipeline import run_offline_research
        path = self.write_csv()
        original_bytes = Path(path).read_bytes()
        from app import offline_research_pipeline
        original_loader = offline_research_pipeline.load_ohlcv_csv

        def mutate_original_after_snapshot(snapshot, **kwargs):
            frame = original_loader(snapshot, **kwargs)
            Path(path).write_text(
                "timestamp,open,high,low,close\\n"
                "2024-01-01T00:00:00Z,10,12,9,11\\n"
                "2024-01-02T00:00:00Z,11,13,10,12\\n"
                "2024-01-03T00:00:00Z,12,14,11,13\\n",
                encoding="utf-8",
            )
            return frame

        with patch("app.offline_research_pipeline.load_ohlcv_csv", side_effect=mutate_original_after_snapshot):
            result = run_offline_research(path, timestamp_column="timestamp")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["source_sha256"], hashlib.sha256(original_bytes).hexdigest())
        with self.assertRaisesRegex(ValueError, "changed after research"):
            from app.offline_research_pipeline import build_offline_evidence_bundle
            build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")

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

    def test_offline_export_rejects_source_changed_after_research(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        path = self.write_csv()
        result = run_offline_research(path, timestamp_column="timestamp")
        Path(path).write_text(
            "timestamp,open,high,low,close\\n"
            "2024-01-01T00:00:00Z,10,12,9,11\\n"
            "2024-01-02T00:00:00Z,11,13,10,12\\n"
            "2024-01-03T00:00:00Z,12,14,11,13\\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "changed after research"):
            build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")

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
            file.write("time_utc,open,high,low,close\n")
            file.write("2024-01-01T00:00:00Z,10,12,9,11\n")
            file.write("2024-01-02T00:00:00Z,11,13,10,12\n")
            path = file.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        result = run_offline_research(path, timestamp_column="time_utc")
        bundle = build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")
        self.assertEqual(bundle["scope"]["observation_count"], 2)
        self.assertEqual(bundle["observations"][0]["timestamp"], "2024-01-01T00:00:00+00:00")


    def test_offline_export_rejects_source_provenance_column_collision(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as file:
            file.write("timestamp,open,high,low,close,source\n")
            file.write("2024-01-01T00:00:00Z,10,12,9,11,original-source\n")
            path = file.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        result = run_offline_research(path, timestamp_column="timestamp")
        with self.assertRaisesRegex(ValueError, "source.*conflicts with source provenance"):
            build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")

    def test_offline_export_rejects_timestamp_field_collision(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as file:
            file.write("time_utc,timestamp,open,high,low,close\n")
            file.write("2024-01-01T00:00:00Z,original-ts,10,12,9,11\n")
            path = file.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        result = run_offline_research(path, timestamp_column="time_utc")
        with self.assertRaisesRegex(ValueError, "timestamp.*conflicts with normalized timestamp"):
            build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")

    def test_offline_export_rejects_unsorted_timestamps_after_dataset_mutation(self):
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        path = self.write_csv()
        result = run_offline_research(path, timestamp_column="timestamp")
        result["dataset"] = result["dataset"].iloc[::-1].reset_index(drop=True)
        with self.assertRaisesRegex(ValueError, "sorted chronologically"):
            build_offline_evidence_bundle(result, symbol="BTCUSD", interval="1d")

    def test_evidence_bundle_round_trip_preserves_integrity_and_provenance(self):
        import json
        from app.offline_research_pipeline import (
            run_offline_research, build_offline_evidence_bundle,
        )
        from app.research_export_compare import compare_research_exports

        path = self.write_csv()
        research = run_offline_research(path, timestamp_column="timestamp")
        bundle = build_offline_evidence_bundle(
            research, symbol="BTCUSD", interval="1d"
        )
        restored = json.loads(json.dumps(bundle, ensure_ascii=False, allow_nan=False))

        comparison = compare_research_exports(bundle, restored)
        self.assertFalse(comparison["different"])
        self.assertEqual(bundle["integrity"]["digest"], restored["integrity"]["digest"])
        self.assertEqual(
            bundle["scope"]["source_sha256"], restored["scope"]["source_sha256"]
        )
        self.assertTrue(comparison["integrity_validation"]["before"]["valid"])
        self.assertTrue(comparison["integrity_validation"]["after"]["valid"])
        self.assertEqual(comparison["counts"]["before"], 2)
        self.assertEqual(comparison["counts"]["after"], 2)

    def test_indicator_pipeline_requires_timestamp_column(self):
        from app.offline_research_pipeline import run_offline_research
        with self.assertRaisesRegex(ValueError, "timestamp_column is required"):
            run_offline_research(self.write_csv(), include_smc=True)


if __name__ == "__main__":
    unittest.main()
