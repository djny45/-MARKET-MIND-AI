"""Documentation links must resolve.

The README is the front door of this project. A landing page full of dead links
undermines the one claim that matters here - that the numbers and statements are
verifiable - so the check runs in the test suite, not only by hand.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_doc_links.py"


class DocumentationLinkTests(unittest.TestCase):
    def test_every_relative_link_in_readme_and_docs_resolves(self):
        result = subprocess.run(
            [sys.executable, str(CHECKER)],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            f"broken documentation links:\n{result.stdout}{result.stderr}",
        )

    def test_readme_keeps_its_essential_sections(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for heading in ("## Quickstart", "## Status (honest)", "## Docs map",
                        "## Architecture at a glance", "## Contributing"):
            self.assertIn(heading, text, f"README lost the {heading!r} section")
        self.assertIn("broker_execution: false", text)
        self.assertIn("docs/assets/readme-hero.jpg", text)

    def test_readme_does_not_promise_live_execution(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
        for banned in ("live trading enabled", "real-money execution",
                       "connect your broker to trade"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
