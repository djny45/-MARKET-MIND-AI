import unittest

from app.research_orchestrator import orchestrate_research


class ResearchOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            {"id": "feed", "type": "market_input",
             "data": {"values": [10, 11, 12, 13, 14, 15]}},
            {"id": "sma", "type": "sma", "data": {"period": 2}},
            {"id": "summary", "type": "research_summary", "data": {}},
        ]
        self.edges = [
            {"source": "feed", "target": "sma"},
            {"source": "sma", "target": "summary"},
        ]

    def test_coordinates_workers_and_builds_single_report(self):
        result = orchestrate_research(self.nodes, self.edges, {})
        self.assertEqual(result["orchestration_status"], "completed")
        self.assertEqual(result["intelligence_core"], "shared_central_intelligence")
        self.assertEqual(result["report"]["summary"]["tasks_completed"], 3)
        self.assertEqual(len(result["report"]["findings"]), 3)
        self.assertEqual(result["report"]["findings"][-1]["node_type"], "research_summary")
        self.assertEqual(result["report"]["findings"][0]["evidence_status"],
                         "source_provenance_not_attached")

    def test_registry_digest_and_capability_boundary_are_included(self):
        result = orchestrate_research(self.nodes, self.edges, {})
        self.assertEqual(len(result["registry_digest_sha256"]), 64)
        self.assertTrue(result["capabilities"]["logical_worker_coordination"])
        self.assertFalse(result["capabilities"]["llm_inference"])
        self.assertFalse(result["capabilities"]["autonomous_learning"])
        self.assertFalse(result["capabilities"]["broker_execution"])
        self.assertEqual(result["model_synthesis"]["status"], "not_configured")
        self.assertIsNone(result["model_synthesis"]["summary"])

    def test_supplied_evidence_is_audited_and_attached_to_report(self):
        claims = [
            {"text": "Claim supported", "claim_key": "audit-key", "stance": "supports",
             "source_refs": ["src-a"]},
            {"text": "Claim contradicted", "claim_key": "audit-key", "stance": "contradicts",
             "source_refs": ["src-b"]},
        ]
        sources = [
            {"source_id": "src-a", "url": "https://source-a.example/report"},
            {"source_id": "src-b", "url": "https://source-b.example/report"},
        ]
        result = orchestrate_research(
            self.nodes, self.edges, {},
            evidence_claims=claims, source_registry=sources,
        )
        audit = result["report"]["evidence_audit"]
        self.assertEqual(audit["metrics"]["claim_disagreement_candidate_count"], 1)
        self.assertEqual(audit["disagreement_candidates"][0]["status"], "human_review_required")
        self.assertTrue(any("does not verify source authenticity" in item
                            for item in result["report"]["limitations"]))

    def test_orchestration_without_claims_reports_audit_unavailable_coverage(self):
        result = orchestrate_research(self.nodes, self.edges, {})
        audit = result["report"]["evidence_audit"]
        self.assertIsNone(audit["metrics"]["claim_reference_coverage"])
        self.assertEqual(audit["metrics"]["claim_disagreement_candidate_count"], 0)

    def test_invalid_workflow_rejected(self):
        with self.assertRaises(ValueError):
            orchestrate_research([{"id": "bad", "type": "unknown"}], [], {})

    def test_failed_task_is_reported_without_fabricating_a_finding(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": ["not numeric"]}},
            {"id": "sma", "type": "sma", "data": {"period": 2}},
        ]
        edges = [{"source": "feed", "target": "sma"}]
        result = orchestrate_research(nodes, edges, {})
        self.assertEqual(result["orchestration_status"], "completed_with_errors")
        self.assertEqual(result["report"]["summary"]["tasks_failed_or_skipped"], 2)
        self.assertEqual(result["report"]["findings"], [])


if __name__ == "__main__":
    unittest.main()
