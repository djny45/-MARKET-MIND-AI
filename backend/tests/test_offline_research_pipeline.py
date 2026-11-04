"""Tests for offline research orchestration."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

available = all(importlib.util.find_spec(name) is not None for name in ("pandas", "numpy"))


@unittest.skipUnless(available, "optional pandas/numpy research dependencies not installed")
class OfflineResearchPipelineTests(unittest.TestCase):
    def test_pipeline_loads_dataset_without_optional_indicators(self):
        from app.offline_research_pipeline import run_offline_research
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as file:
            file.write("timestamp,open,high,low,close\\n")
            file.write("2024-01-01,10,12,9,11\\n")
            file.write("2024-01-02,11,13,10,12\\n")
            path = file.name
        self.addCleanup(Path(path).unlink, missing_ok=True)

        result = run_offline_research(path, timestamp_column="timestamp")
        self.assertEqual(result["row_count"], 2)
        self.assertIn("dataset", result)
        self.assertEqual(result["indicators"], {})


if __name__ == "__main__":
    unittest.main()
