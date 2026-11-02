import unittest

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

    def test_registry_does_not_claim_independent_models_or_broker_execution(self):
        boundary = evaluate_registry()["execution_boundary"]
        self.assertTrue(boundary["profiles_are_templates"])
        self.assertFalse(boundary["independent_models"])
        self.assertFalse(boundary["llm_inference_enabled"])
        self.assertFalse(boundary["broker_execution"])


if __name__ == "__main__":
    unittest.main()
