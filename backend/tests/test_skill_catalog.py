import unittest

from app.skill_catalog import list_skills, load_skill


class SkillCatalogTests(unittest.TestCase):
    def test_catalog_contains_only_allowlisted_research_skills(self):
        skills = list_skills()
        by_id = {skill["id"]: skill for skill in skills}
        self.assertEqual(len(skills), 319)
        self.assertNotIn("trader-broker", by_id)
        self.assertTrue(all(
            skill["mode"] == "research_and_paper_only"
            for skill in skills if skill["id"].startswith("trader-")
        ))
        self.assertTrue(all(
            skill["mode"] == "engineering_research"
            for skill in skills if skill["id"].startswith("rea-") or skill["id"] == "reverse-engineer-anything"
        ))
        self.assertTrue(all(skill["available"] for skill in skills))
        self.assertEqual(by_id["stageshow"]["mode"], "ui_design_only")
        self.assertTrue(by_id["stageshow"]["requires_external_tools"])
        self.assertEqual(by_id["market-data-yahoo"]["mode"], "market_data_research_only")
        self.assertTrue(by_id["market-data-yahoo"]["requires_external_tools"])
        self.assertEqual(by_id["market-data-stooq"]["mode"], "market_data_research_only")
        self.assertTrue(by_id["market-data-stooq"]["requires_external_tools"])


    def test_social_research_skill_is_allowlisted_and_loadable(self):
        skills = {skill["id"]: skill for skill in list_skills()}
        social = skills["social-research"]
        self.assertTrue(social["available"])
        self.assertEqual(social["mode"], "social_research_only")
        self.assertTrue(social["requires_external_tools"])
        loaded = load_skill("social-research")
        self.assertIn("public RSS", loaded["content"])
        self.assertEqual(loaded["mode"], "social_research_only")
        self.assertFalse(loaded["broker_execution"])

    def test_allowlisted_skill_can_be_loaded(self):
        result = load_skill("trader-scanner")
        self.assertIn("content", result)
        self.assertTrue(result["content"].strip())
        self.assertFalse(result["broker_execution"])

    def test_rea_engineering_skills_are_allowlisted_with_tool_boundary(self):
        skills = {skill["id"]: skill for skill in list_skills()}
        for slug in (
            "reverse-engineer-anything",
            "rea-analysis-optimization",
            "rea-ci-tests-audit",
            "rea-tool-design",
        ):
            with self.subTest(slug=slug):
                self.assertIn(slug, skills)
                self.assertTrue(skills[slug]["available"])
                self.assertEqual(skills[slug]["mode"], "engineering_research")
                self.assertTrue(skills[slug]["requires_external_tools"])
                loaded = load_skill(slug)
                self.assertTrue(loaded["content"].strip())
                self.assertTrue(loaded["requires_external_tools"])
                self.assertFalse(loaded["broker_execution"])

    def test_stageshow_is_loadable_but_scoped_to_ui_design(self):
        result = load_skill("stageshow")
        self.assertIn("Stageshow", result["content"])
        self.assertEqual(result["mode"], "ui_design_only")
        self.assertTrue(result["requires_external_tools"])
        self.assertFalse(result["broker_execution"])

    def test_yahoo_market_data_skill_is_loadable_and_research_only(self):
        result = load_skill("market-data-yahoo")
        self.assertIn("Yahoo Finance", result["content"])
        self.assertEqual(result["mode"], "market_data_research_only")
        self.assertFalse(result["broker_execution"])

    def test_stooq_market_data_skill_is_loadable_and_research_only(self):
        result = load_skill("market-data-stooq")
        self.assertIn("Stooq", result["content"])
        self.assertEqual(result["mode"], "market_data_research_only")
        self.assertFalse(result["broker_execution"])

    def test_quant_research_evaluation_skill_is_allowlisted_and_research_only(self):
        skills = {skill["id"]: skill for skill in list_skills()}
        skill = skills["quant-research-evaluation"]
        self.assertTrue(skill["available"])
        self.assertEqual(skill["mode"], "research_evaluation_only")
        self.assertFalse(skill["requires_external_tools"])
        loaded = load_skill("quant-research-evaluation")
        self.assertIn("Chronological separation", loaded["content"])
        self.assertIn("Qlib", loaded["content"])
        self.assertFalse(loaded["broker_execution"])


    def test_300_skill_pack_is_discoverable_and_loads_one_skill_at_a_time(self):
        skills = {skill["id"]: skill for skill in list_skills()}
        self.assertEqual(sum(skill_id.startswith("mm-skill-") for skill_id in skills), 300)
        self.assertIn("mm-skill-001", skills)
        self.assertIn("mm-skill-300", skills)
        loaded = load_skill("mm-skill-001")
        self.assertEqual(loaded["id"], "mm-skill-001")
        self.assertIn("Provider Adapter Design", loaded["content"])
        self.assertEqual(loaded["mode"], "research_evaluation_only")
        self.assertFalse(loaded["broker_execution"])
        self.assertNotIn("### 002.", loaded["content"])

    def test_skill_pack_rejects_out_of_range_ids(self):
        for skill_id in ("mm-skill-000", "mm-skill-301", "mm-skill-999", "mm-skill-01"):
            with self.subTest(skill_id=skill_id):
                with self.assertRaises(KeyError):
                    load_skill(skill_id)

    def test_unknown_and_broker_skills_are_rejected(self):
        for slug in ("trader-broker", "../README.md", "missing-skill"):
            with self.subTest(slug=slug):
                with self.assertRaises(KeyError):
                    load_skill(slug)


if __name__ == "__main__":
    unittest.main()
