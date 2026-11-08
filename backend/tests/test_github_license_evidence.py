import base64
import unittest
from unittest.mock import patch

from app.github_license_evidence import fetch_pinned_license_evidence

SHA = "e" * 40


class PinnedLicenseEvidenceTests(unittest.TestCase):
    def test_fetches_license_at_exact_commit(self):
        license_text = "MIT License\\nCopyright test"
        raw = license_text.encode()
        root = [{"name": "LICENSE", "type": "file", "size": len(raw)}]
        file_obj = {"name": "LICENSE", "type": "file", "size": len(raw),
                    "encoding": "base64", "content": base64.b64encode(raw).decode()}
        with patch("app.github_license_evidence._get_json", side_effect=[{"sha": SHA}, root, file_obj]) as get:
            result = fetch_pinned_license_evidence(
                repository_url="https://github.com/sample/project", commit_sha=SHA)
        self.assertEqual(result["license_text"], license_text)
        self.assertEqual(result["commit_sha"], SHA)
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["legal_conclusion"])
        self.assertEqual(get.call_count, 3)

    def test_returns_not_found_without_claiming_license(self):
        with patch("app.github_license_evidence._get_json", side_effect=[{"sha": SHA}, []]):
            result = fetch_pinned_license_evidence(
                repository_url="https://github.com/sample/project", commit_sha=SHA)
        self.assertFalse(result["license_file_found"])
        self.assertEqual(result["license_evidence_status"], "not_found_at_pinned_root")
        self.assertIsNone(result["license_text"])

    def test_rejects_sha_mismatch_and_bad_url(self):
        with patch("app.github_license_evidence._get_json", return_value={"sha": "f" * 40}):
            with self.assertRaisesRegex(ValueError, "did not match"):
                fetch_pinned_license_evidence(
                    repository_url="https://github.com/sample/project", commit_sha=SHA)
        with self.assertRaises(ValueError):
            fetch_pinned_license_evidence(repository_url="https://example.com/x/y", commit_sha=SHA)

    def test_rejects_large_license(self):
        with patch("app.github_license_evidence._get_json", side_effect=[
            {"sha": SHA}, [{"name": "LICENSE", "type": "file", "size": 30001}]
        ]):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                fetch_pinned_license_evidence(
                    repository_url="https://github.com/sample/project", commit_sha=SHA)


if __name__ == "__main__":
    unittest.main()
