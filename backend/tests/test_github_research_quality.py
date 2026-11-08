import unittest

from app.github_research_quality import score_source_evidence


class GitHubResearchQualityTests(unittest.TestCase):
    def test_complete_provenance_scores_full_but_stays_review_only(self):
        sha = "a" * 40
        url = "https://github.com/org/repo"
        candidate = {
            "repository_url": url, "commit_sha": sha, "file_path": "docs/guide.md",
            "content": "Example docs", "content_sha256": "b" * 64,
            "review_required": True,
        }
        license_evidence = {
            "license_file_found": True, "commit_sha": sha,
            "repository_url": url,
        }
        result = score_source_evidence(candidate, license_evidence)
        self.assertEqual(result["score"], result["max_score"])
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["automatic_promotion"])
        self.assertFalse(result["execution_allowed"])

    def test_missing_license_evidence_reduces_score(self):
        candidate = {
            "repository_url": "https://github.com/org/repo",
            "commit_sha": "a" * 40, "file_path": "README.md",
            "content": "Documentation", "content_sha256": "c" * 64,
            "review_required": True,
        }
        result = score_source_evidence(candidate)
        self.assertEqual(result["score"], 80)
        self.assertFalse(result["checks"][5]["passed"])

    def test_malformed_hashes_and_url_do_not_receive_provenance_points(self):
        candidate = {
            "repository_url": "https://github.com/org/repo/extra",
            "commit_sha": "g" * 40,
            "file_path": "README.md",
            "content": "Documentation",
            "content_sha256": "z" * 64,
            "review_required": True,
        }
        result = score_source_evidence(candidate)
        self.assertFalse(result["checks"][0]["passed"])
        self.assertFalse(result["checks"][1]["passed"])
        self.assertFalse(result["checks"][4]["passed"])
        self.assertEqual(result["score"], 25)

    def test_rejects_non_object(self):
        with self.assertRaises(ValueError):
            score_source_evidence("not a candidate")


if __name__ == "__main__":
    unittest.main()
