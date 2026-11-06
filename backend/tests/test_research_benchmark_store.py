import tempfile
import unittest
from pathlib import Path

from app.research_benchmark import run_offline_research_benchmark
from app.research_benchmark_store import BenchmarkRecordStore


def benchmark_result(source_ref="src-1"):
    return run_offline_research_benchmark([{
        "case_id": "store-test",
        "draft": "Synthetic test draft.",
        "claims": [{"text": "Test claim", "source_refs": [source_ref]}],
        "source_registry": [{"source_id": "src-1"}],
    }])


class BenchmarkRecordStoreTests(unittest.TestCase):
    def test_save_is_idempotent_and_record_can_be_retrieved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BenchmarkRecordStore(Path(directory) / "history.sqlite")
            result = benchmark_result()
            first_id = store.save(result)
            second_id = store.save(result)
            self.assertEqual(first_id, second_id)
            self.assertEqual(len(store.list_records()), 1)
            retrieved = store.get(first_id)
            self.assertEqual(retrieved["result"], result)

    def test_distinct_results_are_stored_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BenchmarkRecordStore(Path(directory) / "history.sqlite")
            first = store.save(benchmark_result("src-1"))
            second = store.save(benchmark_result("unknown"))
            self.assertNotEqual(first, second)
            self.assertEqual(len(store.list_records()), 2)

    def test_unknown_record_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BenchmarkRecordStore(Path(directory) / "history.sqlite")
            self.assertIsNone(store.get("not-present"))

    def test_rejects_invalid_list_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BenchmarkRecordStore(Path(directory) / "history.sqlite")
            for limit in (0, 501, True, "10"):
                with self.subTest(limit=limit):
                    with self.assertRaises(ValueError):
                        store.list_records(limit=limit)


if __name__ == "__main__":
    unittest.main()
