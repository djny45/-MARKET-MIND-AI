import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import (
    OpenSourceIntakeRequest, GitHubResearchQualityRequest,
    register_open_source_candidate, review_open_source_license,
    OpenSourceLicenseReviewDispositionRequest, record_open_source_license_review,
    list_open_source_license_reviews,
)
from app.worker_memory import append_memory, read_memory
from app.open_source_license_review import build_license_review_checklist


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
                "license_file_sha256": hashlib.sha256(b"Apache license text for review.").hexdigest(),
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


    def test_license_review_rejects_tampered_license_text_digest(self):
        intake = register_open_source_candidate("worker_001", self.request())
        candidate = intake["candidate"]
        evidence = {
            "repository_url": candidate["repository_url"],
            "commit_sha": candidate["commit_sha"],
            "license_file_found": True,
            "license_evidence_status": "license_file_found_pending_human_review",
            "license_file_sha256": hashlib.sha256(b"Original license text").hexdigest(),
            "license_text": "Altered license text",
        }
        checklist = build_license_review_checklist(candidate, evidence)
        self.assertFalse(checklist["evidence_match"])
        self.assertFalse(checklist["evidence_digest_valid"])
        self.assertEqual(checklist["evidence_status"], "missing_or_mismatched")
        self.assertFalse(checklist["reuse_approved"])
        self.assertFalse(checklist["execution_allowed"])


    def test_license_review_disposition_is_append_only_and_never_approves_reuse(self):
        intake = register_open_source_candidate("worker_001", self.request())
        candidate = intake["candidate"]
        candidate_memory_id = intake["memory_record"]["memory_id"]
        license_text = "Apache license text for review."
        append_memory(
            "worker_001", "validation_result",
            {
                "record_type": "pinned_github_license_evidence",
                "repository_url": candidate["repository_url"],
                "commit_sha": candidate["commit_sha"],
                "license_file_found": True,
                "license_evidence_status": "license_file_found_pending_human_review",
                "license_file_sha256": hashlib.sha256(license_text.encode("utf-8")).hexdigest(),
                "license_text": license_text,
            },
            ["pinned-license-test"], "unverified",
        )
        checklist_result = review_open_source_license(
            "worker_001", GitHubResearchQualityRequest(candidate_memory_id=candidate_memory_id)
        )
        checklist_memory_id = checklist_result["memory_record"]["memory_id"]
        result = record_open_source_license_review(
            "worker_001",
            OpenSourceLicenseReviewDispositionRequest(
                candidate_memory_id=candidate_memory_id,
                checklist_memory_id=checklist_memory_id,
                reviewer="reviewer-test",
                disposition="refer_to_legal",
                review_note="Ask qualified counsel to review before considering reuse.",
            ),
        )
        review = result["review"]
        self.assertEqual(review["disposition"], "refer_to_legal")
        self.assertEqual(review["review_status"], "human_disposition_recorded_unverified")
        self.assertFalse(review["reviewer_identity_verified"])
        self.assertFalse(review["reuse_approved"])
        self.assertFalse(review["execution_allowed"])
        self.assertFalse(review["automatic_copy_allowed"])
        self.assertFalse(review["legal_conclusion"])
        self.assertEqual(result["memory_record"]["quality_status"], "unverified")

    def test_license_review_disposition_rejects_checklist_for_other_candidate(self):
        intake = register_open_source_candidate("worker_001", self.request())
        candidate_memory_id = intake["memory_record"]["memory_id"]
        other = register_open_source_candidate(
            "worker_001", self.request(repository_url="https://github.com/example/other")
        )
        license_text = "Example license text."
        append_memory(
            "worker_001", "validation_result",
            {
                "record_type": "pinned_github_license_evidence",
                "repository_url": other["candidate"]["repository_url"],
                "commit_sha": other["candidate"]["commit_sha"],
                "license_file_found": True,
                "license_evidence_status": "license_file_found_pending_human_review",
                "license_file_sha256": hashlib.sha256(license_text.encode("utf-8")).hexdigest(),
                "license_text": license_text,
            },
            ["pinned-license-test"], "unverified",
        )
        checklist = review_open_source_license(
            "worker_001", GitHubResearchQualityRequest(candidate_memory_id=other["memory_record"]["memory_id"])
        )
        with self.assertRaises(HTTPException) as error:
            record_open_source_license_review(
                "worker_001",
                OpenSourceLicenseReviewDispositionRequest(
                    candidate_memory_id=candidate_memory_id,
                    checklist_memory_id=checklist["memory_record"]["memory_id"],
                    reviewer="reviewer-test",
                    disposition="reviewed",
                ),
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_license_review_history_endpoint_returns_only_disposition_records(self):
        intake = register_open_source_candidate("worker_001", self.request())
        candidate_memory_id = intake["memory_record"]["memory_id"]
        license_text = "Apache license text for review."
        append_memory(
            "worker_001", "validation_result",
            {
                "record_type": "pinned_github_license_evidence",
                "repository_url": intake["candidate"]["repository_url"],
                "commit_sha": intake["candidate"]["commit_sha"],
                "license_file_found": True,
                "license_evidence_status": "license_file_found_pending_human_review",
                "license_file_sha256": hashlib.sha256(license_text.encode("utf-8")).hexdigest(),
                "license_text": license_text,
            },
            ["pinned-license-test"], "unverified",
        )
        checklist = review_open_source_license(
            "worker_001", GitHubResearchQualityRequest(candidate_memory_id=candidate_memory_id)
        )
        record_open_source_license_review(
            "worker_001",
            OpenSourceLicenseReviewDispositionRequest(
                candidate_memory_id=candidate_memory_id,
                checklist_memory_id=checklist["memory_record"]["memory_id"],
                reviewer="reviewer-test",
                disposition="reviewed",
                review_note="Reviewed for research tracking only.",
            ),
        )
        result = list_open_source_license_reviews("worker_001", limit=10)
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["reviews"][0]["review"]["record_type"],
            "open_source_license_review_disposition",
        )
        self.assertFalse(result["reviews"][0]["review"]["reuse_approved"])
        self.assertFalse(result["reviews"][0]["review"]["execution_allowed"])

    def test_license_review_history_rejects_invalid_limit_and_worker(self):
        with self.assertRaises(HTTPException) as limit_error:
            list_open_source_license_reviews("worker_001", limit=0)
        self.assertEqual(limit_error.exception.status_code, 400)
        with self.assertRaises(HTTPException) as worker_error:
            list_open_source_license_reviews("worker_9999", limit=10)
        self.assertEqual(worker_error.exception.status_code, 400)

    def test_license_review_api_rejects_non_candidate_memory(self):
        with self.assertRaises(HTTPException) as error:
            review_open_source_license(
                "worker_001", GitHubResearchQualityRequest(candidate_memory_id="missing")
            )
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
