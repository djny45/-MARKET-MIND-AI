import os
import tempfile
import asyncio
import unittest
from unittest.mock import patch

from app.analytical_agent_runtime import agent_scope, current_agent_scope

from fastapi import HTTPException
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

    def test_agent_scope_isolated_between_concurrent_async_tasks(self):
        async def run_scope(worker_id, task_id):
            with agent_scope(worker_id, task_id):
                await asyncio.sleep(0)
                return current_agent_scope()

        async def run_all():
            return await asyncio.gather(
                run_scope("worker_001", "task-a"),
                run_scope("worker_002", "task-b"),
            )

        first, second = asyncio.run(run_all())
        self.assertEqual(first["worker_id"], "worker_001")
        self.assertEqual(first["task_id"], "task-a")
        self.assertEqual(first["memory_namespace"], "workers/worker_001")
        self.assertEqual(second["worker_id"], "worker_002")
        self.assertEqual(second["task_id"], "task-b")
        self.assertEqual(second["memory_namespace"], "workers/worker_002")
        self.assertIsNone(current_agent_scope())

    def test_agent_scope_restores_parent_after_nested_scope(self):
        with agent_scope("worker_001", "parent"):
            with agent_scope("worker_002", "child"):
                self.assertEqual(current_agent_scope()["task_id"], "child")
            self.assertEqual(current_agent_scope()["task_id"], "parent")
        self.assertIsNone(current_agent_scope())

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
