import json
import unittest

from app.research_benchmark import run_offline_research_benchmark
from app.research_benchmark_record import (
    RECORD_SCHEMA_VERSION,
    serialize_benchmark_record,
)


def cases():
    return [{
        "case_id": "record-fixture",
        "draft": "Synthetic fixture; limitations are explicit.",
        "claims": [{"text": "Fixture claim", "source_refs": ["src-1"]}],
        "source_registry": [{"source_id": "src-1"}],
    }]


class ResearchBenchmarkRecordTests(unittest.TestCase):
    def test_record_is_versioned_and_deterministic(self):
        result = run_offline_research_benchmark(cases())
        first = serialize_benchmark_record(result)
        second = serialize_benchmark_record(result)
        record = json.loads(first)
        self.assertEqual(first, second)
        self.assertEqual(record["record_schema_version"], RECORD_SCHEMA_VERSION)
        self.assertEqual(record["benchmark_id"], result["benchmark_id"])
        self.assertEqual(record["result"], result)
        self.assertEqual(len(record["record_id"]), 64)

    def test_record_id_changes_when_result_changes(self):
        baseline = run_offline_research_benchmark(cases())
        changed_cases = cases()
        changed_cases[0]["claims"][0]["source_refs"] = ["unknown-source"]
        changed = run_offline_research_benchmark(changed_cases)
        self.assertNotEqual(
            json.loads(serialize_benchmark_record(baseline))["record_id"],
            json.loads(serialize_benchmark_record(changed))["record_id"],
        )

    def test_rejects_invalid_record_inputs(self):
        invalid_results = [
            None,
            {},
            {"benchmark_id": "id", "benchmark_type": "wrong", "case_count": 1,
             "aggregate_metrics": {}},
            {"benchmark_id": "id", "benchmark_type": "offline_research_traceability",
             "case_count": True, "aggregate_metrics": {}},
            {"benchmark_id": "id", "benchmark_type": "offline_research_traceability",
             "case_count": 1, "aggregate_metrics": {}, "bad": object()},
        ]
        for result in invalid_results:
            with self.subTest(result_type=type(result).__name__):
                with self.assertRaises(ValueError):
                    serialize_benchmark_record(result)


if __name__ == "__main__":
    unittest.main()
