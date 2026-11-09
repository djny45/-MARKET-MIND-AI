import unittest

from app.open_source_intake import build_source_candidate
from app.open_source_license_review import build_license_review_checklist


class OpenSourceLicenseReviewTests(unittest.TestCase):
    def candidate(self):
        return build_source_candidate(
            repository_url="https://github.com/example/project",
            commit_sha="a" * 40,
            file_path="docs/readme.md",
            license_spdx="MIT",
            content="Research excerpt with provenance.",
        )

    def evidence(self):
        return {
            "repository_url": "https://github.com/example/project",
            "commit_sha": "a" * 40,
            "license_file_found": True,
            "license_evidence_status": "license_file_found_pending_human_review",
            "license_file_sha256": "d" * 64,
            "license_text": "Example license text.",
        }

    def test_intake_candidate_and_pinned_license_evidence_join_review_only(self):
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

    def test_candidate_content_tampering_is_detected(self):
        candidate = self.candidate()
        candidate["content"] = "altered content"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            build_license_review_checklist(candidate, self.evidence())

    def test_candidate_identifier_tampering_is_detected(self):
        candidate = self.candidate()
        candidate["candidate_id"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "identifier mismatch"):
            build_license_review_checklist(candidate, self.evidence())

    def test_rejects_missing_candidate_provenance(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            build_license_review_checklist({"repository_url": "https://github.com/x/y"}, None)


if __name__ == "__main__":
    unittest.main()
