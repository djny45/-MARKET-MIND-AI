import unittest

from app.skill_catalog import list_skills, load_skill


class SkillCatalogTests(unittest.TestCase):
    def test_catalog_contains_only_allowlisted_research_skills(self):
        skills = list_skills()
        ids = {skill["id"] for skill in skills}
        self.assertEqual(len(skills), 10)
        self.assertNotIn("trader-broker", ids)
        self.assertTrue(all(skill["mode"] == "research_and_paper_only" for skill in skills))
        self.assertTrue(all(skill["available"] for skill in skills))

    def test_allowlisted_skill_can_be_loaded(self):
        result = load_skill("trader-scanner")
        self.assertIn("content", result)
        self.assertTrue(result["content"].strip())
        self.assertFalse(result["broker_execution"])

    def test_unknown_and_broker_skills_are_rejected(self):
        for slug in ("trader-broker", "../README.md", "missing-skill"):
            with self.subTest(slug=slug):
                with self.assertRaises(KeyError):
                    load_skill(slug)


if __name__ == "__main__":
    unittest.main()
