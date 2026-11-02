import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import research_skill_pack as pack


def catalog(*titles):
    return "\n".join(
        f"### {index:03d}. {title}\n\nResearch notes for {title}."
        for index, title in enumerate(titles, start=1)
    )


class ResearchSkillPackValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.catalog_path = Path(self.temp_dir.name) / "SKILL.md"
        self.path_patch = patch.object(pack, "SKILL_PACK_PATH", self.catalog_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def write_catalog(self, text):
        self.catalog_path.write_text(text, encoding="utf-8")

    def valid_catalog(self):
        return catalog(*(f"Research Playbook {index:03d}" for index in range(1, pack.SKILL_COUNT + 1)))

    def test_missing_catalog_is_unavailable_not_partial(self):
        self.assertEqual(pack.list_pack_skills(), [])

    def test_complete_ordered_catalog_is_listed(self):
        self.write_catalog(self.valid_catalog())
        skills = pack.list_pack_skills()
        self.assertEqual(len(skills), pack.SKILL_COUNT)
        self.assertEqual(skills[0]["id"], "mm-skill-001")
        self.assertEqual(skills[-1]["id"], "mm-skill-300")

    def test_incomplete_catalog_is_rejected(self):
        self.write_catalog(catalog("Only one entry"))
        self.assertEqual(pack.list_pack_skills(), [])

    def test_out_of_order_ids_are_rejected(self):
        entries = [f"### {index:03d}. Playbook {index:03d}\n\nContent" for index in range(1, 301)]
        entries[0], entries[1] = entries[1], entries[0]
        self.write_catalog("\n".join(entries))
        self.assertEqual(pack.list_pack_skills(), [])

    def test_duplicate_skill_names_are_rejected(self):
        titles = ["Duplicate"] * pack.SKILL_COUNT
        self.write_catalog(catalog(*titles))
        self.assertEqual(pack.list_pack_skills(), [])

    def test_malformed_heading_does_not_count_as_skill(self):
        text = self.valid_catalog().replace("### 001. Research Playbook 001", "## 001. Research Playbook 001", 1)
        self.write_catalog(text)
        self.assertEqual(pack.list_pack_skills(), [])

    def test_loaded_skill_is_research_only_and_cannot_execute_broker_orders(self):
        self.write_catalog(self.valid_catalog())
        loaded = pack.load_pack_skill("mm-skill-001")
        self.assertEqual(loaded["mode"], "research_evaluation_only")
        self.assertFalse(loaded["broker_execution"])
        self.assertEqual(loaded["id"], "mm-skill-001")
        self.assertNotIn("mm-skill-002", loaded["content"])

    def test_invalid_ids_are_rejected(self):
        self.write_catalog(self.valid_catalog())
        for skill_id in ("mm-skill-000", "mm-skill-301", "mm-skill-abc", "../SKILL.md"):
            with self.subTest(skill_id=skill_id):
                with self.assertRaises(KeyError):
                    pack.load_pack_skill(skill_id)


if __name__ == "__main__":
    unittest.main()
