import unittest

from app.worker_runtime import dispatch_worker_task, worker_capabilities


class WorkerRuntimeTests(unittest.TestCase):
    def test_capability_report_distinguishes_executable_and_template_profiles(self):
        report = worker_capabilities()
        self.assertEqual(report["worker_profiles"], 550)
        self.assertGreater(report["executable_profiles"], 0)
        self.assertEqual(
            report["worker_profiles"],
            report["executable_profiles"] + report["template_only_profiles"],
        )
        self.assertEqual(report["execution_mode"], "synchronous_deterministic")

    def test_authorized_worker_executes_mapped_operation(self):
        result = dispatch_worker_task("worker_001", "sma", [1, 2, 3], {"period": 2})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["operation"], "sma")
        self.assertTrue(result["research_only"])
        self.assertIsNotNone(result["result"])

    def test_worker_cannot_execute_unmapped_operation(self):
        with self.assertRaises(PermissionError):
            dispatch_worker_task("worker_001", "rsi", [1, 2, 3])

    def test_unknown_worker_is_rejected(self):
        with self.assertRaises(KeyError):
            dispatch_worker_task("worker_999", "sma", [1, 2, 3])

    def test_invalid_observation_count_is_rejected(self):
        with self.assertRaises(ValueError):
            dispatch_worker_task("worker_001", "sma", [1])


if __name__ == "__main__":
    unittest.main()
