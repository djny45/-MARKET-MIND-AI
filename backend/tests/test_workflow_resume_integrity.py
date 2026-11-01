import unittest

from fastapi import HTTPException

from app.main import _validate_checkpoint_integrity, _workflow_request_fingerprint


class WorkflowResumeIntegrityTests(unittest.TestCase):
    def test_request_fingerprint_is_stable_for_mapping_order(self):
        left = {"nodes": [{"id": "a", "type": "market_input"}], "inputs": {"data": [1, 2]}}
        right = {"inputs": {"data": [1, 2]}, "nodes": [{"type": "market_input", "id": "a"}]}
        self.assertEqual(_workflow_request_fingerprint(left), _workflow_request_fingerprint(right))

    def test_request_fingerprint_changes_when_inputs_change(self):
        first = {"nodes": [{"id": "a"}], "inputs": {"data": [1, 2]}}
        changed = {"nodes": [{"id": "a"}], "inputs": {"data": [1, 2, 3]}}
        self.assertNotEqual(_workflow_request_fingerprint(first), _workflow_request_fingerprint(changed))

    def _valid_checkpoint(self):
        request = {"nodes": [{"id": "a", "type": "market_input"}], "inputs": {"data": [1, 2]}}
        checkpoint = {
            "request_fingerprint": _workflow_request_fingerprint(request),
            "completed_node_ids": ["a"],
            "results": {"a": {"values": [1, 2]}},
            "tasks": {"a": {"status": "completed"}},
        }
        return request, checkpoint

    def test_checkpoint_integrity_accepts_matching_completed_task(self):
        request, checkpoint = self._valid_checkpoint()
        _validate_checkpoint_integrity(request, checkpoint, {"a"})

    def test_checkpoint_integrity_rejects_changed_inputs(self):
        request, checkpoint = self._valid_checkpoint()
        changed = {"nodes": request["nodes"], "inputs": {"data": [9, 8]}}
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(changed, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_missing_task_result(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["results"] = {}
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
