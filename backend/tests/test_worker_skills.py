import unittest

from app.workers import list_workers


class WorkerSkillRoutingTests(unittest.TestCase):
    def test_all_worker_templates_have_explicit_skill_routing_field(self):
        workers = list_workers()
        self.assertGreaterEqual(len(workers), 550)
        self.assertTrue(all(worker["kind"] == "ai_analytical_worker" for worker in workers))
        self.assertTrue(all(worker["model"] == "shared_central_intelligence" for worker in workers))
        self.assertTrue(all(isinstance(worker["skill_refs"], list) for worker in workers))
        self.assertTrue(all("stageshow" not in worker["skill_refs"] for worker in workers))
        self.assertTrue(all(sum(ref.startswith("mm-skill-") for ref in worker["skill_refs"]) == 2 for worker in workers))
        pack_refs = {ref for worker in workers for ref in worker["skill_refs"] if ref.startswith("mm-skill-")}
        self.assertEqual(len(pack_refs), 300)

    def test_ui_only_skill_is_not_assigned_to_analytical_workers(self):
        for worker in list_workers():
            self.assertNotIn("stageshow", worker["skill_refs"])

    def test_specialist_departments_map_to_relevant_playbooks(self):
        by_department = {}
        for worker in list_workers():
            by_department.setdefault(worker["department"], worker["skill_refs"])
        self.assertIn("trader-scanner", by_department["technical_analysis"])
        self.assertIn("trader-analyst", by_department["equities_fundamentals"])
        self.assertIn("trader-news", by_department["news_intelligence"])
        self.assertIn("trader-risk", by_department["risk_analytics"])

    def test_rea_playbooks_are_routed_to_relevant_engineering_workers(self):
        by_department = {}
        for worker in list_workers():
            by_department.setdefault(worker["department"], worker["skill_refs"])
        self.assertIn("rea-ci-tests-audit", by_department["data_quality"])
        self.assertIn("rea-ci-tests-audit", by_department["research_validation"])
        for skill in ("rea-analysis-optimization", "reverse-engineer-anything", "rea-tool-design"):
            self.assertIn(skill, by_department["research_validation"])
        self.assertNotIn("rea-tool-design", by_department["technical_analysis"])

    def test_no_worker_is_granted_broker_execution_skill(self):
        for worker in list_workers():
            self.assertNotIn("trader-broker", worker["skill_refs"])


if __name__ == "__main__":
    unittest.main()
