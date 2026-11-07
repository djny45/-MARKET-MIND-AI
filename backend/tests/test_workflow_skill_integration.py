import unittest

from fastapi import HTTPException

from app.main import WorkflowRequest, run_workflow


class WorkflowSkillIntegrationTests(unittest.TestCase):
    def test_selected_research_skill_is_loaded_into_workflow_context(self):
        request = WorkflowRequest(
            nodes=[{"id": "input", "type": "market_input", "data": {"values": [10, 11, 12]}}],
            edges=[],
            inputs={},
            skill_ids=["trader-scanner"],
        )
        result = run_workflow(request)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["skill_context_mode"], "research_and_paper_only")
        self.assertEqual([item["id"] for item in result["skill_context"]], ["trader-scanner"])
        self.assertIn("content", result["skill_context"][0])
        self.assertFalse(result["skill_context"][0]["broker_execution"])


    def test_workflow_can_select_one_catalog_skill_without_loading_the_pack(self):
        request = WorkflowRequest(
            nodes=[{"id": "input", "type": "market_input", "data": {"values": [100, 101, 99]}}],
            edges=[],
            inputs={},
            skill_ids=["mm-skill-002"],
        )
        result = run_workflow(request)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([item["id"] for item in result["skill_context"]], ["mm-skill-002"])
        self.assertIn("API Contract Normalization", result["skill_context"][0]["content"])
        self.assertNotIn("### 003.", result["skill_context"][0]["content"])
        self.assertFalse(result["skill_context"][0]["broker_execution"])

    def test_workflow_loads_qlib_research_skill_as_advisory_context(self):
        request = WorkflowRequest(
            nodes=[{"id": "input", "type": "market_input", "data": {"values": [100, 101, 99, 102]}}],
            edges=[],
            inputs={},
            skill_ids=["qlib-research"],
        )
        result = run_workflow(request)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["skill_context_mode"], "research_and_paper_only")
        self.assertEqual([item["id"] for item in result["skill_context"]], ["qlib-research"])
        skill = result["skill_context"][0]
        self.assertIn("chronological train/validation/test", skill["content"])
        self.assertEqual(skill["mode"], "research_evaluation_only")
        self.assertFalse(skill["broker_execution"])
        self.assertTrue(skill["content"].strip())
        protocols = result["skill_protocols"]
        self.assertEqual(len(protocols), 1)
        protocol = protocols[0]
        self.assertEqual(protocol["protocol_id"], "qlib-historical-evaluation-v1")
        self.assertEqual(protocol["mode"], "advisory_checklist")
        self.assertIn("chronological train/validation/test", " ".join(protocol["steps"]))
        self.assertIn("Baseline and candidate metrics with sample counts", protocol["required_outputs"])
        self.assertTrue(protocol["research_only"])
        self.assertFalse(protocol["broker_execution"])
        self.assertFalse(protocol["autonomous_model_update"])
        self.assertIn("not_automatically_applied", protocol["enforcement"])

    def test_qlib_protocol_is_not_attached_when_skill_not_selected(self):
        request = WorkflowRequest(
            nodes=[{"id": "input", "type": "market_input", "data": {"values": [5, 6, 7]}}],
            edges=[],
            inputs={},
        )
        result = run_workflow(request)
        self.assertEqual(result["skill_protocols"], [])

    def test_workflow_rejects_broker_or_unknown_skill(self):
        request = WorkflowRequest(
            nodes=[{"id": "input", "type": "market_input", "data": {"values": [10, 11]}}],
            skill_ids=["trader-broker"],
        )
        with self.assertRaises(HTTPException) as error:
            run_workflow(request)
        self.assertEqual(error.exception.status_code, 400)

    def test_workflow_rejects_duplicate_skill_ids(self):
        request = WorkflowRequest(
            nodes=[{"id": "input", "type": "market_input", "data": {"values": [10, 11]}}],
            skill_ids=["trader-scanner", "trader-scanner"],
        )
        with self.assertRaises(HTTPException) as error:
            run_workflow(request)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
