import unittest

from app.open_source_license_review import build_license_review_checklist


class OpenSourceLicenseReviewTests(unittest.TestCase):
    def candidate(self):
        return {
            "candidate_id": "c" * 64,
            "repository_url": "https://github.com/example/project",
            "commit_sha": "a" * 40,
            "license_spdx": "MIT",
            "content_sha256": "b" * 64,
        }

    def evidence(self):
        return {
            "repository_url": "https://github.com/example/project",
            "commit_sha": "a" * 40,
            "license_file_found": True,
            "license_evidence_status": "license_file_found_pending_human_review",
            "license_file_sha256": "d" * 64,
            "license_text": "Example license text.",
        }

    def test_exact_pinned_evidence_creates_blank_review_only_checklist(self):
        result = build_license_review_checklist(self.candidate(), self.evidence())
        self.assertTrue(result["evidence_match"])
        self.assertEqual(result["review_status"], "pending_human_review")
        self.assertFalse(result["reuse_approved"])
        self.assertFalse(result["execution_allowed"])
        self.assertTrue(all(item["checked"] is None for item in result["checklist"]))

    def test_mismatched_commit_is_not_matched_or_approved(self):
        evidence = self.evidence()
        evidence["commit_sha"] = "e" * 40
        result = build_license_review_checklist(self.candidate(), evidence)
        self.assertFalse(result["evidence_match"])
        self.assertEqual(result["evidence_status"], "missing_or_mismatched")
        self.assertFalse(result["reuse_approved"])

    def test_missing_license_text_requires_review(self):
        evidence = self.evidence()
        evidence["license_text"] = " "
        result = build_license_review_checklist(self.candidate(), evidence)
        self.assertFalse(result["evidence_match"])

    def test_rejects_missing_candidate_provenance(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            build_license_review_checklist({"repository_url": "https://github.com/x/y"}, None)


if __name__ == "__main__":
    unittest.main()
