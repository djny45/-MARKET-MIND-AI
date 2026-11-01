import unittest

from app.worker_coordinator import delegate_worker_tasks


class WorkerCoordinatorTests(unittest.TestCase):
    def test_delegates_dependency_chain_between_authorized_workers(self):
        result = delegate_worker_tasks([
            {"task_id": "smooth", "operation": "sma", "params": {"period": 2}},
            {"task_id": "momentum", "operation": "rsi", "depends_on": ["smooth"], "params": {"period": 2}},
        ], [10, 11, 12, 13, 14])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["execution_order"], ["smooth", "momentum"])
        self.assertEqual(result["completed_count"], 2)
        self.assertEqual(result["tasks"][1]["depends_on"], ["smooth"])

    def test_rejects_cycles(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            delegate_worker_tasks([
                {"task_id": "a", "operation": "sma", "depends_on": ["b"]},
                {"task_id": "b", "operation": "ema", "depends_on": ["a"]},
            ], [1, 2, 3])

    def test_rejects_unauthorized_worker_operation(self):
        with self.assertRaises(PermissionError):
            delegate_worker_tasks([
                {"task_id": "x", "operation": "rsi", "worker_id": "worker_001"},
            ], [1, 2, 3])

    def test_rejects_missing_dependencies(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            delegate_worker_tasks([
                {"task_id": "x", "operation": "sma", "depends_on": ["missing"]},
            ], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
