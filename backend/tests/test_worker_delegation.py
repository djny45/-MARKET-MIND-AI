import unittest
from app.worker_delegation import delegate_worker_tasks

class WorkerDelegationTests(unittest.TestCase):
    def test_authorized_tasks_execute_in_order(self):
        result = delegate_worker_tasks([
            {"task_id":"trend-1","worker_id":"worker_001","operation":"sma",
             "values":[1,2,3],"params":{"period":2}}
        ])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["tasks"][0]["status"], "completed")

    def test_rejects_unauthorized_worker_operation(self):
        with self.assertRaises(PermissionError):
            delegate_worker_tasks([{"task_id":"bad","worker_id":"worker_001",
                                    "operation":"rsi","values":[1,2,3]}])

    def test_rejects_forward_or_unknown_dependency(self):
        with self.assertRaises(ValueError):
            delegate_worker_tasks([{"task_id":"next","worker_id":"worker_001",
                                    "operation":"sma","depends_on":"missing","values":[1,2,3]}])

if __name__ == "__main__":
    unittest.main()
