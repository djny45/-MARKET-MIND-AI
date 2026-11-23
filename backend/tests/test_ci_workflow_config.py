"""Guards for the CI quality workflow's Trivy scan scope.

These checks are deliberately dependency-free: CI installs only the declared
backend requirements, so the assertions parse the workflow as structured text
rather than relying on an optional YAML package.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "quality.yml"


class TrivyWorkflowConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def _trivy_job(self) -> str:
        match = re.search(r"^  trivy-security:\n(?P<body>(?:^    .*\n|^      .*\n|^        .*\n|^          .*\n|^            .*\n)*)", self.text, re.M)
        self.assertIsNotNone(match, "trivy-security job missing from quality.yml")
        return match.group("body")

    def test_workflow_has_least_privilege_permissions(self):
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertNotIn("write-all", self.text)

    def test_workflow_syntax_has_no_tabs_and_consistent_indentation(self):
        self.assertNotIn("\t", self.text)
        for line in self.text.splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                indent = len(line) - len(line.lstrip(" "))
                self.assertEqual(indent % 2, 0, f"odd indentation: {line!r}")

    def test_trivy_job_scans_vulnerabilities_misconfigurations_and_secrets(self):
        job = self._trivy_job()
        self.assertIn("scanners: vuln,misconfig,secret", job)

    def test_trivy_job_uses_medium_high_critical_and_fails_closed(self):
        job = self._trivy_job()
        self.assertGreaterEqual(job.count("severity: MEDIUM,HIGH,CRITICAL"), 2)
        self.assertGreaterEqual(job.count("exit-code: '1'"), 2)
        self.assertNotIn("ignore-unfixed: true", job)
        self.assertNotIn("continue-on-error", job)

    def test_trivy_job_covers_filesystem_and_configuration(self):
        job = self._trivy_job()
        self.assertIn("scan-type: fs", job)
        self.assertIn("scan-type: config", job)
        self.assertGreaterEqual(job.count("uses: aquasecurity/trivy-action@v0.36.0"), 2)

    def test_workflow_triggers_include_feature_branches(self):
        self.assertIn("branches: [main, 'feat/**', 'feature/**']", self.text)


if __name__ == "__main__":
    unittest.main()
