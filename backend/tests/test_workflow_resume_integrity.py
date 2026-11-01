import unittest

from fastapi import HTTPException
from unittest.mock import patch

from app.main import _validate_checkpoint_integrity, _workflow_request_fingerprint, resume_workflow_run


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
            "checkpoint_schema_version": 1,
            "checkpointed_at": "2026-01-01T00:00:00+00:00",
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

    def test_checkpoint_integrity_rejects_non_list_completed_ids(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["completed_node_ids"] = "a"
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_duplicate_completed_ids(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["completed_node_ids"] = ["a", "a"]
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_non_mapping_results_and_tasks(self):
        request, checkpoint = self._valid_checkpoint()
        for field in ("results", "tasks"):
            with self.subTest(field=field):
                invalid = dict(checkpoint)
                invalid[field] = []
                with self.assertRaises(HTTPException) as error:
                    _validate_checkpoint_integrity(request, invalid, {"a"})
                self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_non_mapping_task_record(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["tasks"]["a"] = "completed"
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_unsupported_schema_version(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["checkpoint_schema_version"] = 99
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_invalid_timestamp(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["checkpointed_at"] = "not-a-timestamp"
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_mismatched_task_identity(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["tasks"]["a"]["node_id"] = "different-node"
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_invalid_completed_layer_count(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["completed_layers"] = True
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_malformed_uncompleted_task_record(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["tasks"]["unrelated"] = "not-a-task-record"
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a", "unrelated"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_result_not_marked_completed(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["results"]["a"] = {"values": [1, 2]}
        checkpoint["completed_node_ids"] = []
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_checkpoint_integrity_rejects_unknown_task_node(self):
        request, checkpoint = self._valid_checkpoint()
        checkpoint["tasks"]["ghost"] = {"node_id": "ghost", "status": "queued"}
        with self.assertRaises(HTTPException) as error:
            _validate_checkpoint_integrity(request, checkpoint, {"a"})
        self.assertEqual(error.exception.status_code, 409)

    def test_resume_rejects_corrupted_persisted_checkpoint(self):
        record = {
            "request": {"nodes": [], "edges": [], "inputs": {}},
            "checkpoint": {},
            "checkpoint_error": "Stored checkpoint is malformed; it cannot be used for recovery.",
        }
        with patch("app.main.workspace.get_execution", return_value=record):
            with self.assertRaises(HTTPException) as error:
                resume_workflow_run("broken-run")
        self.assertEqual(error.exception.status_code, 409)

    def test_resume_rejects_corrupted_persisted_request(self):
        record = {
            "request": {},
            "checkpoint": {},
            "request_error": "Stored workflow request is malformed; it cannot be replayed.",
        }
        with patch("app.main.workspace.get_execution", return_value=record):
            with self.assertRaises(HTTPException) as error:
                resume_workflow_run("broken-request")
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
