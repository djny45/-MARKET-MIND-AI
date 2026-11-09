import unittest

from app.github_research_review_bundle import build_review_bundle


class GitHubResearchReviewBundleTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "memory_id": "candidate-1",
            "content": {
                "record_type": "open_source_learning_candidate",
                "repository_url": "https://github.com/org/repo",
                "commit_sha": "a" * 40,
                "file_path": "docs/readme.md",
                "content_sha256": "b" * 64,
            },
        }
        self.records = [
            {"memory_id": "chunk-1", "content": {
                "record_type": "github_research_chunk_manifest",
                "source_memory_id": "candidate-1", "source_sha256": "b" * 64,
            }},
            {"memory_id": "score-1", "content": {
                "record_type": "github_research_evidence_quality",
                "candidate_memory_id": "candidate-1", "score": 100,
                "max_score": 100, "score_type": "provenance_completeness_heuristic",
            }},
            {"memory_id": "license-1", "content": {
                "record_type": "pinned_github_license_evidence",
                "repository_url": "https://github.com/org/repo",
                "commit_sha": "a" * 40, "license_file_found": True,
                "license_evidence_status": "license_file_found_pending_human_review",
                "license_file_sha256": __import__("hashlib").sha256(b"Example pinned license text").hexdigest(),
                "license_text": "Example pinned license text",
            }},
        ]

    def test_complete_bundle_is_ready_for_review_not_promotion(self):
        bundle = build_review_bundle(self.candidate, self.records)
        self.assertEqual(bundle["review_status"], "ready_for_human_review")
        self.assertEqual(bundle["provenance_score"], 100)
        self.assertTrue(bundle["chunk_manifest_matches_source"])
        self.assertTrue(bundle["human_review_required"])
        self.assertFalse(bundle["automatic_promotion"])
        self.assertFalse(bundle["execution_allowed"])
        self.assertEqual(len(bundle["bundle_sha256"]), 64)
        self.assertEqual(bundle["bundle_sha256"], build_review_bundle(self.candidate, self.records)["bundle_sha256"])

    def test_untyped_or_mislinked_score_cannot_make_bundle_ready(self):
        records = [dict(item, content=dict(item["content"])) for item in self.records]
        records[1]["content"]["score_type"] = "unverified_quality_rating"
        bundle = build_review_bundle(self.candidate, records)
        self.assertEqual(bundle["review_status"], "evidence_incomplete")
        self.assertFalse(bundle["provenance_score_record_valid"])
        self.assertIn("valid_provenance_score_record", bundle["missing_evidence"])
        self.assertIsNone(bundle["provenance_score"])

    def test_bundle_digest_changes_when_pinned_license_evidence_changes(self):
        import hashlib
        changed = [dict(item, content=dict(item["content"])) for item in self.records]
        changed_text = "Updated pinned license evidence"
        changed[2]["content"]["license_text"] = changed_text
        changed[2]["content"]["license_file_sha256"] = hashlib.sha256(changed_text.encode()).hexdigest()
        original_bundle = build_review_bundle(self.candidate, self.records)
        changed_bundle = build_review_bundle(self.candidate, changed)
        self.assertTrue(changed_bundle["license_evidence_digest_valid"])
        self.assertNotEqual(original_bundle["license_evidence_sha256"], changed_bundle["license_evidence_sha256"])
        self.assertNotEqual(original_bundle["bundle_sha256"], changed_bundle["bundle_sha256"])

    def test_missing_or_mismatched_evidence_blocks_readiness(self):
        records = self.records[:]
        records[0] = {"memory_id": "chunk-1", "content": {
            "record_type": "github_research_chunk_manifest",
            "source_memory_id": "candidate-1", "source_sha256": "c" * 64,
        }}
        bundle = build_review_bundle(self.candidate, records[:2])
        self.assertEqual(bundle["review_status"], "evidence_incomplete")
        self.assertIn("matching_chunk_manifest", bundle["missing_evidence"])
        self.assertIn("license_evidence", bundle["missing_evidence"])

    def test_tampered_license_evidence_digest_blocks_review_readiness(self):
        records = [dict(item, content=dict(item["content"])) for item in self.records]
        records[2]["content"]["license_text"] = "changed license text"
        records[2]["content"]["license_file_sha256"] = "d" * 64
        records[2]["content"]["license_evidence_status"] = "license_file_found_pending_human_review"
        bundle = build_review_bundle(self.candidate, records)
        self.assertEqual(bundle["review_status"], "evidence_incomplete")
        self.assertFalse(bundle["license_evidence_digest_valid"])
        self.assertIn("valid_license_file_evidence", bundle["missing_evidence"])
        self.assertFalse(bundle["execution_allowed"])

    def test_missing_source_identity_blocks_review_readiness(self):
        candidate = {
            "memory_id": "candidate-1",
            "content": {
                "record_type": "open_source_learning_candidate",
                "repository_url": None,
                "commit_sha": None,
                "file_path": "",
                "content_sha256": None,
            },
        }
        bundle = build_review_bundle(candidate, [
            {"memory_id": "chunk", "content": {
                "record_type": "github_research_chunk_manifest",
                "source_memory_id": "candidate-1", "source_sha256": None,
            }},
            {"memory_id": "score", "content": {
                "record_type": "github_research_evidence_quality",
                "candidate_memory_id": "candidate-1", "score": 80,
                "max_score": 100, "score_type": "provenance_completeness_heuristic",
            }},
            {"memory_id": "license", "content": {
                "record_type": "pinned_github_license_evidence",
                "repository_url": None, "commit_sha": None,
                "license_file_found": True,
                "license_evidence_status": "license_file_found_pending_human_review",
                "license_file_sha256": "e" * 64,
                "license_text": "License text",
            }},
        ])
        self.assertEqual(bundle["review_status"], "evidence_incomplete")
        self.assertIn("valid_source_identity", bundle["missing_evidence"])

    def test_rejects_wrong_candidate_type(self):
        with self.assertRaisesRegex(ValueError, "not an open-source"):
            build_review_bundle({"memory_id": "x", "content": {"record_type": "other"}}, [])


if __name__ == "__main__":
    unittest.main()
