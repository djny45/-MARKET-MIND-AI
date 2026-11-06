"""Smoke test for the bundled synthetic offline CSV example."""
import importlib.util
import unittest
from pathlib import Path

available = all(importlib.util.find_spec(name) is not None for name in ("pandas", "numpy"))


@unittest.skipUnless(available, "optional pandas/numpy research dependencies not installed")
class SyntheticDatasetExampleTests(unittest.TestCase):
    def test_example_loads_and_is_marked_synthetic(self):
        from app.offline_dataset import load_ohlcv_csv

        backend_dir = Path(__file__).resolve().parents[1]
        sample = backend_dir / "examples" / "synthetic_ohlcv.csv"
        frame = load_ohlcv_csv(sample, timestamp_column="timestamp")

        self.assertEqual(len(frame), 20)
        self.assertTrue(frame["timestamp"].is_monotonic_increasing)
        self.assertTrue({"open", "high", "low", "close", "volume"}.issubset(frame.columns))


if __name__ == "__main__":
    unittest.main()
