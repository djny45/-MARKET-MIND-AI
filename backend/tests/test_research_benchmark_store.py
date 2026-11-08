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

    def test_retrieval_rejects_database_index_metadata_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "history.sqlite"
            store = BenchmarkRecordStore(database)
            record_id = store.save(benchmark_result())
            import sqlite3
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE research_benchmark_records SET benchmark_id = ? WHERE record_id = ?",
                    ("tampered", record_id),
                )
            with self.assertRaisesRegex(ValueError, "benchmark ID does not match database index"):
                store.get(record_id)

    def test_retrieval_rejects_malformed_record_json(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "history.sqlite"
            store = BenchmarkRecordStore(database)
            record_id = store.save(benchmark_result())
            import sqlite3
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE research_benchmark_records SET record_json = ? WHERE record_id = ?",
                    ("{broken", record_id),
                )
            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                store.get(record_id)

    def test_retrieval_rejects_nested_payload_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "history.sqlite"
            store = BenchmarkRecordStore(database)
            record_id = store.save(benchmark_result())
            import json
            import sqlite3
            with sqlite3.connect(database) as connection:
                row = connection.execute(
                    "SELECT record_json FROM research_benchmark_records WHERE record_id = ?",
                    (record_id,),
                ).fetchone()
                record = json.loads(row[0])
                record["result"]["case_count"] = 999
                connection.execute(
                    "UPDATE research_benchmark_records SET record_json = ? WHERE record_id = ?",
                    (json.dumps(record), record_id),
                )
            with self.assertRaisesRegex(ValueError, "content does not match its record ID"):
                store.get(record_id)

    def test_in_memory_store_persists_across_operations(self):
        store = BenchmarkRecordStore(":memory:")
        record_id = store.save(benchmark_result())
        self.assertIsNotNone(store.get(record_id))
        self.assertEqual(len(store.list_records()), 1)

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
