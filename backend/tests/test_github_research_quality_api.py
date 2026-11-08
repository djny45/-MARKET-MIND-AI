import unittest
from unittest.mock import patch

from app import main


class GitHubResearchEvidenceApiTests(unittest.TestCase):
    def test_quality_endpoint_reads_candidate_and_matching_license(self):
        sha = "a" * 40
        repo_url = "https://github.com/org/repo"
        candidate = {
            "record_type": "open_source_learning_candidate",
            "repository_url": repo_url, "commit_sha": sha,
            "file_path": "docs.md", "content": "text",
            "content_sha256": "b" * 64, "review_required": True,
        }
        candidate_record = {"memory_id": "candidate-1", "content": candidate}
        license_record = {"memory_id": "license-1", "content": {
            "record_type": "pinned_github_license_evidence",
            "repository_url": repo_url, "commit_sha": sha,
            "license_file_found": True,
        }}
        with patch.object(main, "read_memory", return_value={
                "memory": [candidate_record, license_record]}), \
             patch.object(main, "append_memory", return_value={"memory_id": "score-1"}) as append:
            result = main.score_open_source_evidence(
                "worker_001",
                main.GitHubResearchQualityRequest(candidate_memory_id="candidate-1"),
            )
        self.assertEqual(result["quality_score"]["score"], 100)
        self.assertFalse(result["quality_score"]["automatic_promotion"])
        append.assert_called_once()

    def test_quality_endpoint_rejects_wrong_memory_record(self):
        with patch.object(main, "read_memory", return_value={
                "memory": [{"memory_id": "candidate-1", "content": {"record_type": "other"}}]}):
            with self.assertRaises(main.HTTPException) as caught:
                main.score_open_source_evidence(
                    "worker_001",
                    main.GitHubResearchQualityRequest(candidate_memory_id="candidate-1"),
                )
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
