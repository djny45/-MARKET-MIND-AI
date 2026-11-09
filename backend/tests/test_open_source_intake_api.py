import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import (\n    OpenSourceIntakeRequest, GitHubResearchQualityRequest,\n    register_open_source_candidate, review_open_source_license,\n)
from app.worker_memory import append_memory, read_memory


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

    def test_license_review_api_persists_pending_checklist_for_matching_evidence(self):
        intake = register_open_source_candidate("worker_001", self.request())
        candidate = intake["candidate"]
        candidate_memory_id = intake["memory_record"]["memory_id"]
        append_memory(
            "worker_001", "validation_result",
            {
                "record_type": "pinned_github_license_evidence",
                "repository_url": candidate["repository_url"],
                "commit_sha": candidate["commit_sha"],
                "license_file_found": True,
                "license_evidence_status": "license_file_found_pending_human_review",
                "license_file_sha256": "d" * 64,
                "license_text": "Apache license text for review.",
            },
            ["pinned-license-test"], "unverified",
        )
        result = review_open_source_license(
            "worker_001", GitHubResearchQualityRequest(
                candidate_memory_id=candidate_memory_id
            )
        )
        checklist = result["checklist"]
        self.assertTrue(checklist["evidence_match"])
        self.assertEqual(checklist["review_status"], "pending_human_review")
        self.assertFalse(checklist["reuse_approved"])
        self.assertFalse(checklist["execution_allowed"])
        self.assertEqual(result["memory_record"]["quality_status"], "unverified")
        saved = read_memory("worker_001", "validation_result")
        self.assertTrue(any(
            item["content"].get("record_type") == "open_source_license_review_checklist"
            for item in saved["memory"]
        ))

    def test_license_review_api_rejects_non_candidate_memory(self):
        with self.assertRaises(HTTPException) as error:
            review_open_source_license(
                "worker_001", GitHubResearchQualityRequest(candidate_memory_id="missing")
            )
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
