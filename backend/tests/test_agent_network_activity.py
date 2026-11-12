import os
import tempfile
import unittest
from unittest.mock import patch

from app.analytical_agent_tasks import enqueue_research_task, list_recent_task_activity, agent_task_performance, agent_research_quality_performance, agent_supervisor_recommendations, _persist_quality_evaluation

class AgentNetworkActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "activity.sqlite")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_recent_activity_snapshot_aggregates_task_states(self):
        queued = enqueue_research_task("worker_007", "network activity test")
        snapshot = list_recent_task_activity(limit=20)
        self.assertGreaterEqual(snapshot["task_count"], 1)
        self.assertEqual(snapshot["status_counts"]["queued"], 1)
        self.assertEqual(snapshot["latest_by_agent"]["worker_007"]["task_id"], queued["task_id"])
        self.assertEqual(snapshot["source"], "persisted_sqlite_task_records_and_audit_events")

    def test_recent_activity_includes_task_queued_audit_event(self):
        queued = enqueue_research_task("worker_008", "audit in activity view")
        snapshot = list_recent_task_activity(limit=20)
        matching = [event for event in snapshot["recent_audit_events"]
                    if event["task_id"] == queued["task_id"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["event_type"], "task_queued")
        self.assertEqual(snapshot["audit_event_count"], len(snapshot["recent_audit_events"]))

    def test_agent_task_performance_reports_descriptive_persisted_counts(self):
        enqueue_research_task("worker_009", "performance dashboard fixture")
        report = agent_task_performance(limit=20)
        self.assertEqual(report["task_count"], 1)
        self.assertEqual(report["agents"]["worker_009"]["queued"], 1)
        self.assertEqual(report["agents"]["worker_009"]["task_count"], 1)
        self.assertIsNone(report["agents"]["worker_009"]["completion_rate"])
        self.assertIn("not a capability or intelligence score", report["performance_boundary"])

    def test_agent_task_performance_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            agent_task_performance(limit=0)

    def test_research_quality_performance_averages_persisted_traceability(self):
        first = enqueue_research_task("worker_009", "quality fixture one")
        second = enqueue_research_task("worker_009", "quality fixture two")
        _persist_quality_evaluation(first["task_id"], "worker_009", {
            "metrics": {"claim_reference_coverage": 0.75, "known_source_reference_coverage": 0.5}
        })
        _persist_quality_evaluation(second["task_id"], "worker_009", {
            "metrics": {"claim_reference_coverage": 1.0, "known_source_reference_coverage": 0.75}
        })
        report = agent_research_quality_performance(limit=20)
        item = report["agents"]["worker_009"]
        self.assertEqual(item["evaluation_count"], 2)
        self.assertEqual(item["claim_reference_coverage_mean"], 0.875)
        self.assertEqual(item["known_source_reference_coverage_mean"], 0.625)
        self.assertIn("does not establish", report["quality_boundary"])

    def test_research_quality_performance_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            agent_research_quality_performance(limit=551)

    def test_research_quality_api_returns_persisted_metrics(self):
        from app.main import agent_network_research_quality
        queued = enqueue_research_task("worker_009", "quality route fixture")
        _persist_quality_evaluation(queued["task_id"], "worker_009", {
            "metrics": {"claim_reference_coverage": 0.5, "known_source_reference_coverage": 1.0}
        })
        report = agent_network_research_quality(limit=20)
        self.assertEqual(report["evaluations_examined"], 1)
        self.assertEqual(report["agents"]["worker_009"]["claim_reference_coverage_mean"], 0.5)
        self.assertIn("factual accuracy", report["quality_boundary"])

    def test_research_quality_api_translates_invalid_limit_to_http_400(self):
        from fastapi import HTTPException
        from app.main import agent_network_research_quality
        with self.assertRaises(HTTPException) as raised:
            agent_network_research_quality(limit=551)
        self.assertEqual(raised.exception.status_code, 400)

    def test_supervisor_recommendations_are_advisory_and_require_minimum_evidence(self):
        report = agent_supervisor_recommendations(limit=20)
        self.assertEqual(report["decision_mode"], "advisory_only")
        self.assertEqual(report["minimum_evidence"]["finished_tasks"], 5)
        self.assertIn("not measures of intelligence", " ".join(report["limitations"]))
        self.assertEqual(report["recommendation_count"], len(report["recommendations"]))

    def test_supervisor_recommendations_apply_evidence_thresholds(self):
        task_report = {
            "task_count": 10,
            "agents": {
                "worker_review": {
                    "finished_count": 5, "failure_rate": 0.4,
                },
                "worker_observe": {
                    "finished_count": 5, "failure_rate": 0.05,
                },
                "worker_insufficient": {
                    "finished_count": 4, "failure_rate": 0.5,
                },
            },
        }
        quality_report = {
            "agents": {
                "worker_review": {
                    "evaluation_count": 3,
                    "known_source_reference_coverage_mean": 0.5,
                },
                "worker_observe": {
                    "evaluation_count": 3,
                    "known_source_reference_coverage_mean": 0.95,
                },
                "worker_insufficient": {
                    "evaluation_count": 2,
                    "known_source_reference_coverage_mean": 0.1,
                },
            },
        }
        with patch("app.analytical_agent_tasks.agent_task_performance", return_value=task_report), \
             patch("app.analytical_agent_tasks.agent_research_quality_performance", return_value=quality_report):
            report = agent_supervisor_recommendations(limit=20)
        reasons = {(item["agent_id"], item["reason_code"]) for item in report["recommendations"]}
        self.assertIn(("worker_review", "repeated_task_failures"), reasons)
        self.assertIn(("worker_review", "low_source_reference_coverage"), reasons)
        self.assertIn(("worker_observe", "consistent_structural_traceability"), reasons)
        self.assertFalse(any(agent == "worker_insufficient" for agent, _ in reasons))
        self.assertEqual(report["decision_mode"], "advisory_only")

    def test_supervisor_recommendations_reject_invalid_limit(self):
        with self.assertRaises(ValueError):
            agent_supervisor_recommendations(limit=551)

    def test_supervisor_recommendations_api_returns_advisory_payload(self):
        from app.main import agent_network_recommendations
        report = agent_network_recommendations(limit=20)
        self.assertEqual(report["decision_mode"], "advisory_only")
        self.assertIn("recommendations", report)

    def test_supervisor_recommendations_api_translates_invalid_limit_to_http_400(self):
        from fastapi import HTTPException
        from app.main import agent_network_recommendations
        with self.assertRaises(HTTPException) as raised:
            agent_network_recommendations(limit=551)
        self.assertEqual(raised.exception.status_code, 400)

    def test_recent_activity_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            list_recent_task_activity(limit=0)
