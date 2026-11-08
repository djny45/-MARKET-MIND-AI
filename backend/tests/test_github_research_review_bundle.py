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
            }},
            {"memory_id": "license-1", "content": {
                "record_type": "pinned_github_license_evidence",
                "repository_url": "https://github.com/org/repo",
                "commit_sha": "a" * 40, "license_file_found": True,
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
            }},
            {"memory_id": "license", "content": {
                "record_type": "pinned_github_license_evidence",
                "repository_url": None, "commit_sha": None,
                "license_file_found": True,
            }},
        ])
        self.assertEqual(bundle["review_status"], "evidence_incomplete")
        self.assertIn("valid_source_identity", bundle["missing_evidence"])

    def test_rejects_wrong_candidate_type(self):
        with self.assertRaisesRegex(ValueError, "not an open-source"):
            build_review_bundle({"memory_id": "x", "content": {"record_type": "other"}}, [])


if __name__ == "__main__":
    unittest.main()
