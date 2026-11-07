"""Tests for static, non-executing repository review report parsing."""
import unittest
from unittest.mock import patch

from app.repository_review_report import (
    _parse_dependencies,
    build_repository_review_report,
)


class RepositoryReviewReportTests(unittest.TestCase):
    def test_parse_requirements_with_pins(self):
        deps = _parse_dependencies("requirements.txt", "requests>=2.0\n# comment\nhttpx==0.27")
        self.assertEqual([item["name"] for item in deps], ["requests", "httpx"])
        self.assertEqual(deps[1]["specifier"], "==0.27")

    def test_parse_package_json_dependency_sections(self):
        deps = _parse_dependencies("package.json", '{"dependencies":{"react":"^18"},"devDependencies":{"vite":"^5"}}')
        self.assertEqual({item["name"] for item in deps}, {"react", "vite"})

    def test_parse_pyproject_project_dependencies(self):
        deps = _parse_dependencies("pyproject.toml", '[project]\ndependencies=["fastapi>=0.1", "httpx"]')
        self.assertEqual({item["name"] for item in deps}, {"fastapi", "httpx"})

    def test_invalid_manifest_is_reported_not_executed(self):
        deps = _parse_dependencies("package.json", "{invalid json")
        self.assertEqual(deps[0]["name"], "(manifest parse error)")

    def test_report_pins_and_marks_approval_incomplete(self):
        tree = {
            "source_url": "https://github.com/acme/demo",
            "pinned_commit_sha": "a" * 40,
            "entry_count": 2,
            "entries": [
                {"path": "main.py", "category": "source", "language": "Python"},
                {"path": "requirements.txt", "category": "dependency_manifest"},
            ],
        }
        files = {
            "pinned_commit_sha": "a" * 40,
            "files": [{
                "path": "requirements.txt", "status": "retrieved",
                "content": "fastapi>=0.1", "sha256": "b" * 64,
            }],
        }
        with patch("app.repository_review_report.scan_repository_tree", return_value=tree), \
             patch("app.repository_review_report.fetch_review_files", return_value=files):
            result = build_repository_review_report("https://github.com/acme/demo")
        self.assertEqual(result["pinned_commit_sha"], "a" * 40)
        self.assertEqual(result["summary"]["parsed_dependency_count"], 1)
        self.assertFalse(result["analysis_policy"]["license_approved"])
        self.assertFalse(result["analysis_policy"]["dependency_installation_or_execution"])


if __name__ == "__main__":
    unittest.main()
