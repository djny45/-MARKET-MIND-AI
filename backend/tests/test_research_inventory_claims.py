"""Documentation counts must match the runtime registry and skill catalog."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.skill_catalog import list_skills
from app.worker_registry import EXPECTED_CORE, EXPECTED_WORKER_COUNT
from app.workers import list_workers

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / ".agents" / "skills" / "market-mind-300-research-skills" / "SKILL.md"


class ResearchInventoryClaimTests(unittest.TestCase):
    def test_runtime_counts_match_the_verified_inventory(self):
        workers = list_workers()
        self.assertEqual(len(workers), EXPECTED_WORKER_COUNT)
        self.assertEqual(len(workers), 550)
        self.assertEqual(len({worker["department"] for worker in workers}), 20)
        self.assertEqual(len({worker["specialty"] for worker in workers}), 28)
        self.assertEqual(len(list_skills()), 326)
        self.assertEqual(len(re.findall(r"^### \d{3}\. ", PACK.read_text(encoding="utf-8"), re.M)), 300)

    def test_worker_profiles_share_one_core_and_are_templates(self):
        workers = list_workers()
        self.assertTrue(all(worker["model"] == "shared_central_intelligence" for worker in workers))
        self.assertTrue(all(worker["status"] == "template" for worker in workers))
        self.assertEqual(EXPECTED_CORE, "shared_central_intelligence")

    def test_documentation_does_not_repeat_the_old_arithmetic_or_skill_claims(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        registry_doc = (ROOT / "docs" / "WORKER-REGISTRY.md").read_text(encoding="utf-8")
        self.assertIn("20 departments and 28 specialties", readme)
        self.assertIn("560-cell", readme)
        self.assertNotIn("20 departments × 28 specialties", readme)
        self.assertNotIn("550+", readme)
        self.assertNotIn("300+ composable skills", readme)
        self.assertIn("326 entries", registry_doc)
        self.assertIn("89 of those are Vibe Trading reference skills", registry_doc)


if __name__ == "__main__":
    unittest.main()
