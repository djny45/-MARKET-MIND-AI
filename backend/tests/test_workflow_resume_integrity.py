from app.main import _workflow_request_fingerprint


def test_request_fingerprint_is_stable_for_mapping_order():
    left = {"nodes": [{"id": "a", "type": "market_input"}], "inputs": {"data": [1, 2]}}
    right = {"inputs": {"data": [1, 2]}, "nodes": [{"type": "market_input", "id": "a"}]}
    assert _workflow_request_fingerprint(left) == _workflow_request_fingerprint(right)


def test_request_fingerprint_changes_when_inputs_change():
    first = {"nodes": [{"id": "a"}], "inputs": {"data": [1, 2]}}
    changed = {"nodes": [{"id": "a"}], "inputs": {"data": [1, 2, 3]}}
    assert _workflow_request_fingerprint(first) != _workflow_request_fingerprint(changed)


import pytest
from fastapi import HTTPException
from app.main import _validate_checkpoint_integrity


def _valid_checkpoint():
    request = {"nodes": [{"id": "a", "type": "market_input"}], "inputs": {"data": [1, 2]}}
    fingerprint = _workflow_request_fingerprint(request)
    checkpoint = {
        "request_fingerprint": fingerprint,
        "completed_node_ids": ["a"],
        "results": {"a": {"values": [1, 2]}},
        "tasks": {"a": {"status": "completed"}},
    }
    return request, checkpoint


def test_checkpoint_integrity_accepts_matching_completed_task():
    request, checkpoint = _valid_checkpoint()
    _validate_checkpoint_integrity(request, checkpoint, {"a"})


def test_checkpoint_integrity_rejects_changed_inputs():
    request, checkpoint = _valid_checkpoint()
    changed = {"nodes": request["nodes"], "inputs": {"data": [9, 8]}}
    with pytest.raises(HTTPException) as error:
        _validate_checkpoint_integrity(changed, checkpoint, {"a"})
    assert error.value.status_code == 409


def test_checkpoint_integrity_rejects_missing_task_result():
    request, checkpoint = _valid_checkpoint()
    checkpoint["results"] = {}
    with pytest.raises(HTTPException) as error:
        _validate_checkpoint_integrity(request, checkpoint, {"a"})
    assert error.value.status_code == 409
