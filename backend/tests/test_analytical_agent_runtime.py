import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from app.analytical_agent_runtime import MAX_CONTEXT_CHARS, brain_config
from app.main import (
    AgentLearningFeedbackRequest,
    AgentUpdateProposalRequest,
    analytical_agent_brain,
    analytical_agent_learning_feedback,
    analytical_agent_runtime,
    analytical_agent_update_proposal,
)


class AnalyticalAgentRuntimeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "agent-runtime.sqlite")
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_runtime_describes_550_distinct_contexts_without_claiming_independent_models(self):
        result = analytical_agent_runtime()
        self.assertEqual(result["agent_count"], 550)
        self.assertEqual(result["agent_brains"], "distinct_role_context_and_namespace")
        self.assertFalse(result["autonomous_weight_training"])
        self.assertFalse(result["paper_trading"])
        self.assertFalse(result["broker_execution"])

    def test_brain_context_is_worker_specific(self):
        first = analytical_agent_brain("worker_001")
        second = analytical_agent_brain("worker_002")
        self.assertNotEqual(first["brain_context_sha256"], second["brain_context_sha256"])
        self.assertEqual(first["memory_namespace"], "workers/worker_001")
        self.assertFalse(first["independent_model"])

    def test_brain_context_loads_assigned_skills_within_budget(self):
        brain = brain_config("worker_001")
        self.assertEqual(brain["loaded_skill_count"], len(brain["skill_refs"]))
        self.assertIn("autohedge-director-coordination", brain["skill_refs"])
        self.assertIn("autohedge-quant-analysis", brain["skill_refs"])
        self.assertIn("ASSIGNED RESEARCH PLAYBOOKS", brain["brain_context"])
        self.assertIn("AutoHedge-derived", brain["brain_context"])
        self.assertLessEqual(len(brain["brain_context"]), MAX_CONTEXT_CHARS)
        self.assertTrue(brain["brain_context_sha256"])
        self.assertFalse(brain["broker_execution"])

    def test_brain_context_is_isolated_to_worker_skill_assignments(self):
        first = brain_config("worker_001")
        another = brain_config("worker_020")
        self.assertNotEqual(first["skill_refs"], another["skill_refs"])
        self.assertNotEqual(first["brain_context_sha256"], another["brain_context_sha256"])

    def test_unknown_agent_brain_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            analytical_agent_brain("worker_9999")
        self.assertEqual(error.exception.status_code, 404)

    def test_learning_feedback_is_persisted_as_reviewable_memory_not_training(self):
        request = AgentLearningFeedbackRequest(
            summary="Analytical output missed a timestamp caveat.",
            outcome="partially_helpful",
            metrics={"coverage": 0.75},
        )
        result = analytical_agent_learning_feedback("worker_001", request)
        self.assertEqual(result["status"], "recorded_for_future_evaluation")
        self.assertFalse(result["model_training"])
        self.assertTrue(result["memory_id"])

    def test_update_proposal_is_pending_review_and_not_applied(self):
        request = AgentUpdateProposalRequest(
            title="Add source timestamp check",
            rationale="Recent review identified missing timestamp context.",
            proposed_change="Require a timestamp caveat in the output checklist.",
            evidence_refs=["review-note:001"],
        )
        result = analytical_agent_update_proposal("worker_001", request)
        self.assertEqual(result["status"], "pending_review")
        self.assertFalse(result["applied"])
        self.assertEqual(result["proposal"]["auto_apply"], False)

    def test_update_proposal_rejects_unknown_worker(self):
        request = AgentUpdateProposalRequest(
            title="Proposal", rationale="Reason", proposed_change="Change"
        )
        with self.assertRaises(HTTPException) as error:
            analytical_agent_update_proposal("worker_9999", request)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
