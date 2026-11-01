import unittest

from app.central_orchestrator import coordinate_research


class CentralOrchestrationTests(unittest.TestCase):
    def test_combines_worker_dag_and_market_evidence(self):
        findings = [
            {"market_group": market, "topic": "macro", "finding_key": "risk_note",
             "finding_value": "stable", "quality_status": "partial",
             "worker_id": f"{market}-worker", "source_refs": [f"source:{market}"]}
            for market in ("india", "us", "crypto", "forex")
        ]
        result = coordinate_research(
            [{"task_id": "trend", "operation": "sma", "params": {"period": 2}}],
            [10, 11, 12, 13], findings,
        )
        self.assertEqual(result["status"], "ready_for_human_review")
        self.assertEqual(result["worker_delegation"]["status"], "completed")
        self.assertEqual(result["research_brief"]["missing_market_groups"], [])
        self.assertTrue(result["coordination_policy"]["human_review_required"])

    def test_missing_market_coverage_blocks_review_ready_status(self):
        finding = {"market_group": "india", "topic": "macro", "finding_key": "x",
                   "finding_value": 1, "quality_status": "partial",
                   "worker_id": "worker", "source_refs": ["source:india"]}
        result = coordinate_research(
            [{"task_id": "trend", "operation": "sma"}],
            [1, 2, 3], [finding],
        )
        self.assertEqual(result["status"], "incomplete_or_blocked")


if __name__ == "__main__":
    unittest.main()
