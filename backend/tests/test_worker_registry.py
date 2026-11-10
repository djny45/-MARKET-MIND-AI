import unittest
from unittest.mock import patch

from app.worker_registry import (
    EXPECTED_CORE, EXPECTED_WORKER_COUNT, REGISTRY_VERSION,
    evaluate_registry, registry_manifest,
)


class WorkerRegistryTests(unittest.TestCase):
    def test_registry_contains_550_profiles_on_one_core(self):
        result = evaluate_registry()
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["worker_count"], EXPECTED_WORKER_COUNT)
        self.assertEqual(result["shared_intelligence_core"], EXPECTED_CORE)
        self.assertEqual(sum(result["department_counts"].values()), EXPECTED_WORKER_COUNT)
        self.assertEqual(len(result["department_counts"]), 20)
        coverage = result["research_pack_skill_coverage"]
        self.assertEqual(coverage["catalog_pack_skill_count"], 300)
        self.assertEqual(coverage["assigned_unique_pack_skill_count"], 300)
        self.assertEqual(coverage["coverage_ratio"], 1.0)
        self.assertEqual(coverage["missing_pack_skill_ids"], [])
        self.assertEqual(sum(result["skill_reference_counts_by_department"].values()),
                         result["total_skill_reference_count"])

    def test_registry_manifest_is_versioned_and_hashed(self):
        manifest = registry_manifest()
        self.assertEqual(manifest["registry_version"], REGISTRY_VERSION)
        self.assertEqual(len(manifest["profile_digest_sha256"]), 64)
        self.assertTrue(manifest["valid"])

    def test_registry_evaluation_is_deterministic(self):
        first = evaluate_registry()
        second = evaluate_registry()
        self.assertEqual(first["profile_digest_sha256"], second["profile_digest_sha256"])
        self.assertEqual(first["department_counts"], second["department_counts"])

    def test_registry_reports_malformed_profiles_without_crashing(self):
        malformed = [
            {"id": "worker_001", "name": "bad", "department": "unknown",
             "specialty": "test", "kind": "template", "model": EXPECTED_CORE,
             "memory_namespace": "bad", "skill_refs": "not-a-list", "status": "active"},
            None,
        ]
        with patch("app.worker_registry.list_workers", return_value=malformed):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("agent_profile_not_an_object", result["errors"])
        self.assertIn("invalid_worker_skill_references", result["errors"])
        self.assertIn("agent_count_mismatch", result["errors"])

    def test_registry_handles_null_skill_reference_list(self):
        profile = {
            "id": "worker_001", "name": "bad", "department": "data_quality",
            "specialty": "test", "kind": "template", "model": EXPECTED_CORE,
            "memory_namespace": "bad", "skill_refs": None, "status": "active",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("invalid_worker_skill_references", result["errors"])
        self.assertEqual(result["total_skill_reference_count"], 0)

    def test_registry_reports_non_object_profile(self):
        with patch("app.worker_registry.list_workers", return_value=["invalid-profile"]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("agent_profile_not_an_object", result["errors"])
        self.assertIn("agent_ids_not_contiguous_or_ordered", result["errors"])

    def test_registry_rejects_empty_required_profile_values(self):
        profile = {
            "id": "worker_001", "name": "  ", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": [], "status": "template",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("agent_profile_invalid_required_field_values", result["errors"])

    def test_registry_rejects_non_template_worker_profiles(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": [], "status": "active",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("agent_profile_status_mismatch", result["errors"])

    def test_registry_rejects_unknown_worker_kind(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "generic", "model": EXPECTED_CORE,
            "memory_namespace": "workers/test", "skill_refs": [], "status": "template",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("agent_profile_kind_mismatch", result["errors"])

    def test_registry_flags_assigned_skill_missing_from_disk(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": ["test-skill"], "status": "template",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=[
                 {"id": "test-skill", "available": False}
             ]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("assigned_skill_unavailable", result["errors"])
        self.assertEqual(
            result["skill_availability"]["assigned_unavailable_skill_ids"],
            ["test-skill"],
        )
        self.assertFalse(result["skill_availability"]["all_assigned_skills_available"])

    def test_department_domain_matrix_is_explicitly_coverage_not_alignment(self):
        result = evaluate_registry()
        matrix = result["department_skill_domain_matrix"]
        self.assertEqual(
            matrix["status"],
            "catalog_domain_coverage_only_not_semantic_alignment",
        )
        self.assertEqual(matrix["catalog_domain_count"], 15)
        self.assertEqual(len(matrix["departments"]), 20)
        self.assertEqual(matrix["unmapped_assigned_skill_count"], 0)
        for department, item in matrix["departments"].items():
            with self.subTest(department=department):
                self.assertEqual(
                    sum(item["domain_skill_counts"].values()),
                    item["assigned_unique_pack_skill_count"],
                )
                self.assertEqual(item["unmapped_pack_skill_ids"], [])

    def test_registry_does_not_claim_semantic_skill_alignment(self):
        result = evaluate_registry()
        self.assertEqual(result["specialty_skill_alignment"]["status"], "not_evaluated")
        self.assertIn("do not establish semantic alignment",
                      result["specialty_skill_alignment"]["note"])

    def test_registry_does_not_claim_independent_models_or_broker_execution(self):
        boundary = evaluate_registry()["execution_boundary"]
        self.assertTrue(boundary["profiles_are_templates"])
        self.assertFalse(boundary["independent_models"])
        self.assertFalse(boundary["llm_inference_enabled"])
        self.assertFalse(boundary["broker_execution"])


    def test_registry_rejects_unknown_skill_reference(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": ["unknown-skill"], "status": "template",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=[]):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("unknown_skill_reference", result["errors"])

    def test_registry_rejects_duplicate_skill_references(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": ["known-skill", "known-skill"], "status": "template",
        }
        catalog = [{"id": "known-skill", "available": True}]
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=catalog):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("duplicate_worker_skill_reference", result["errors"])

    def test_registry_rejects_non_string_skill_reference(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": ["known-skill", 42], "status": "template",
        }
        catalog = [{"id": "known-skill", "available": True}]
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=catalog):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("invalid_worker_skill_references", result["errors"])


    def test_registry_rejects_duplicate_skill_catalog_ids(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": ["known-skill"], "status": "template",
        }
        catalog = [
            {"id": "known-skill", "available": True},
            {"id": "known-skill", "available": True},
        ]
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=catalog):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("duplicate_skill_catalog_id", result["errors"])
        self.assertEqual(
            result["skill_catalog_integrity"]["duplicate_skill_ids"],
            ["known-skill"],
        )

    def test_registry_reports_malformed_skill_catalog_entries(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": [], "status": "template",
        }
        catalog = [
            {"id": "valid-skill", "available": True},
            {"id": "", "available": "yes"},
            None,
        ]
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=catalog):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("invalid_skill_catalog_entry", result["errors"])
        self.assertEqual(
            result["skill_catalog_integrity"]["malformed_entry_indexes"],
            [1, 2],
        )


    def test_registry_rejects_non_list_skill_catalog(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": [], "status": "template",
        }
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=None):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("skill_catalog_not_a_list", result["errors"])
        self.assertEqual(result["skill_catalog_integrity"]["catalog_entry_count"], 0)

    def test_registry_requires_boolean_catalog_availability_flag(self):
        profile = {
            "id": "worker_001", "name": "Test Worker", "department": "data_quality",
            "specialty": "test", "kind": "ai_analytical_worker",
            "model": EXPECTED_CORE, "memory_namespace": "workers/test",
            "skill_refs": ["known-skill"], "status": "template",
        }
        catalog = [{"id": "known-skill", "available": 1}]
        with patch("app.worker_registry.list_workers", return_value=[profile]), \
             patch("app.worker_registry.list_skills", return_value=catalog):
            result = evaluate_registry()
        self.assertFalse(result["valid"])
        self.assertIn("invalid_skill_catalog_entry", result["errors"])
        self.assertEqual(
            result["skill_catalog_integrity"]["malformed_entry_indexes"],
            [0],
        )


if __name__ == "__main__":
    unittest.main()
