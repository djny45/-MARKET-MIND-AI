"""Tests for static dependency name overlap hints."""
import unittest

from app.repository_compatibility import build_compatibility_report


class RepositoryCompatibilityTests(unittest.TestCase):
    def test_name_overlap_is_ecosystem_scoped_and_requires_review(self):
        candidate = {
            "source_url": "https://github.com/example/demo",
            "pinned_commit_sha": "abc123",
            "dependencies": [
                {"name": "Pandas", "specifier": ">=2", "source_file": "requirements.txt"},
                {"name": "react", "specifier": "^18", "source_file": "package.json",
                 "ecosystem": "npm"},
                {"name": "requests", "specifier": ">=2", "source_file": "requirements.txt"},
            ],
        }
        project = [
            {"name": "pandas", "specifier": ">=1.5", "source_file": "backend/requirements.txt"},
            {"name": "react", "specifier": "^17", "source_file": "frontend/package.json",
             "ecosystem": "npm"},
            {"name": "requests", "specifier": ">=2", "source_file": "backend/requirements.txt"},
        ]
        report = build_compatibility_report(candidate, project)
        self.assertEqual(report["name_overlap_count"], 3)
        self.assertTrue(report["dependencies"][0]["project_name_match"])
        self.assertEqual(report["dependencies"][1]["ecosystem"], "npm")
        self.assertFalse(report["approval"]["install_allowed"])
        self.assertTrue(report["approval"]["human_review_required"])

    def test_missing_name_is_not_matched(self):
        report = build_compatibility_report(
            {"dependencies": [{"specifier": ">=1"}]}, []
        )
        self.assertEqual(report["dependency_count_evaluated"], 0)
        self.assertEqual(report["name_overlap_count"], 0)


if __name__ == "__main__":
    unittest.main()
