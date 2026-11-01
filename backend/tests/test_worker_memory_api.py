import os
import tempfile
import unittest

from fastapi import HTTPException
from unittest.mock import patch

from app.main import WorkerMemoryRequest, add_worker_memory, get_worker_memory


class WorkerMemoryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "api-worker-memory.sqlite")
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_api_functions_append_and_read_worker_memory(self):
        request = WorkerMemoryRequest(
            memory_type="validation_result",
            content={"check": "finite_values", "result": "pass"},
            source_refs=["test-run:unit-01"],
            quality_status="verified_by_importer",
        )
        saved = add_worker_memory("worker_001", request)
        result = get_worker_memory("worker_001", None, 10)
        self.assertEqual(saved["worker_id"], "worker_001")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memory"][0]["content"]["result"], "pass")
        self.assertIn("not verified truth", result["note"])

    def test_api_rejects_unknown_worker(self):
        request = WorkerMemoryRequest(memory_type="observation", content={"note": "x"})
        with self.assertRaises(Exception):
            add_worker_memory("worker_9999", request)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
