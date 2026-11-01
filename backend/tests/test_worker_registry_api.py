import unittest

from app.main import worker_registry


class WorkerRegistryApiTests(unittest.TestCase):
    def test_registry_endpoint_exposes_manifest_and_integrity_evaluation(self):
        result = worker_registry()
        self.assertEqual(result["manifest"]["registry_version"], "1.0.0")
        self.assertEqual(result["manifest"]["worker_count"], 550)
        self.assertEqual(result["evaluation"]["department_count"], 20)
        self.assertTrue(result["evaluation"]["valid"])
        self.assertEqual(len(result["manifest"]["profile_digest_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
