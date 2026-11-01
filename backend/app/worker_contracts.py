"""Versioned typed contracts for deterministic research workflow workers.

Contracts describe data shapes and evidence expectations. They do not imply
model inference, trade recommendations, or broker capabilities.
"""
from copy import deepcopy

CONTRACT_VERSION = "1.0.0"

# Shape names are intentionally small and stable; numerical domain validation
# remains in workflow._numbers and the indicator implementations.
_CONTRACTS = {
    "market_input": {
        "input": {"kind": "numeric_series_or_object", "required": False},
        "output": {"kind": "object", "required_keys": ["values"]},
        "evidence_requirements": ["input_source", "retrieval_timestamp", "quality_status"],
    },
    "data_quality": {
        "input": {"kind": "numeric_series_or_object", "required": True},
        "output": {"kind": "object", "required_keys": ["data", "quality"]},
        "evidence_requirements": ["input_source", "retrieval_timestamp"],
    },
    "sma": {"input": {"kind": "numeric_series_or_object", "required": True},
            "output": {"kind": "object", "required_keys": ["series", "period"]},
            "evidence_requirements": ["input_source", "retrieval_timestamp", "period"]},
    "ema": {"input": {"kind": "numeric_series_or_object", "required": True},
            "output": {"kind": "object", "required_keys": ["series", "period"]},
            "evidence_requirements": ["input_source", "retrieval_timestamp", "period"]},
    "rsi": {"input": {"kind": "numeric_series_or_object", "required": True},
            "output": {"kind": "object", "required_keys": ["series", "period"]},
            "evidence_requirements": ["input_source", "retrieval_timestamp", "period"]},
    "macd": {"input": {"kind": "numeric_series_or_object", "required": True},
             "output": {"kind": "object", "required_keys": ["macd", "signal", "histogram"]},
             "evidence_requirements": ["input_source", "retrieval_timestamp"]},
    "bollinger": {"input": {"kind": "numeric_series_or_object", "required": True},
                  "output": {"kind": "object", "required_keys": ["middle", "upper", "lower"]},
                  "evidence_requirements": ["input_source", "retrieval_timestamp", "period"]},
    "returns": {"input": {"kind": "numeric_series_or_object", "required": True},
                "output": {"kind": "object", "required_keys": ["series", "summary"]},
                "evidence_requirements": ["input_source", "retrieval_timestamp"]},
    "volatility": {"input": {"kind": "numeric_series_or_object", "required": True},
                   "output": {"kind": "number_or_object", "required_keys": []},
                   "evidence_requirements": ["input_source", "retrieval_timestamp"]},
    "research_summary": {"input": {"kind": "numeric_series_or_object", "required": True},
                         "output": {"kind": "object", "required_keys": ["report"]},
                         "evidence_requirements": ["input_source", "retrieval_timestamp", "quality_status"]},
}


def get_worker_contract(node_type: str) -> dict:
    """Return a defensive copy of the versioned contract for a node type."""
    if node_type not in _CONTRACTS:
        raise ValueError(f"No worker contract is defined for node type: {node_type}")
    return {
        "contract_version": CONTRACT_VERSION,
        "node_type": node_type,
        **deepcopy(_CONTRACTS[node_type]),
    }


def validate_worker_input(node_type: str, payload) -> None:
    contract = get_worker_contract(node_type)
    if payload is None and not contract["input"]["required"]:
        return
    if not isinstance(payload, (list, dict)):
        raise ValueError(f"{node_type} input contract requires a list or object")


def validate_worker_output(node_type: str, output) -> None:
    contract = get_worker_contract(node_type)
    shape = contract["output"]["kind"]
    if shape == "number_or_object":
        if isinstance(output, bool) or not isinstance(output, (int, float, dict)):
            raise ValueError(f"{node_type} output contract requires a number or object")
        return
    if not isinstance(output, dict):
        raise ValueError(f"{node_type} output contract requires an object")
    missing = set(contract["output"]["required_keys"]) - set(output)
    if missing:
        raise ValueError(f"{node_type} output is missing contract keys: {', '.join(sorted(missing))}")
