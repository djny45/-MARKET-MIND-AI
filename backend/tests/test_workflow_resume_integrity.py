from app.main import _workflow_request_fingerprint


def test_request_fingerprint_is_stable_for_mapping_order():
    left = {"nodes": [{"id": "a", "type": "market_input"}], "inputs": {"data": [1, 2]}}
    right = {"inputs": {"data": [1, 2]}, "nodes": [{"type": "market_input", "id": "a"}]}
    assert _workflow_request_fingerprint(left) == _workflow_request_fingerprint(right)


def test_request_fingerprint_changes_when_inputs_change():
    first = {"nodes": [{"id": "a"}], "inputs": {"data": [1, 2]}}
    changed = {"nodes": [{"id": "a"}], "inputs": {"data": [1, 2, 3]}}
    assert _workflow_request_fingerprint(first) != _workflow_request_fingerprint(changed)
