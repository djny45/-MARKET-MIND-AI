import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import OpenSourceIntakeRequest, register_open_source_candidate
from app.worker_memory import read_memory


class OpenSourceIntakeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "open-source-intake.sqlite")
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def request(self, **overrides):
        values = {
            "repository_url": "https://github.com/example/research",
            "commit_sha": "b" * 40,
            "file_path": "docs/guide.md",
            "license_spdx": "Apache-2.0",
            "content": "Source excerpt for a research method.",
            "source_kind": "documentation",
        }
        values.update(overrides)
        return OpenSourceIntakeRequest(**values)

    def test_api_persists_source_candidate_as_unverified_pending_memory(self):
        result = register_open_source_candidate("worker_001", self.request())
        candidate = result["candidate"]
        self.assertEqual(candidate["review_status"], "pending")
        self.assertFalse(candidate["execution_allowed"])
        self.assertFalse(candidate["automatic_copy_allowed"])
        self.assertEqual(result["memory_record"]["quality_status"], "unverified")
        stored = read_memory("worker_001", "validation_result")
        self.assertEqual(stored["count"], 1)
        self.assertEqual(
            stored["memory"][0]["content"]["record_type"],
            "open_source_learning_candidate",
        )

    def test_api_rejects_invalid_license_and_unknown_worker(self):
        with self.assertRaises(HTTPException) as license_error:
            register_open_source_candidate(
                "worker_001", self.request(license_spdx="GPL-3.0-only")
            )
        self.assertEqual(license_error.exception.status_code, 400)

        with self.assertRaises(HTTPException) as worker_error:
            register_open_source_candidate("worker_9999", self.request())
        self.assertEqual(worker_error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
