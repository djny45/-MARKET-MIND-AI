import unittest

from app.worker_contracts import (
    CONTRACT_VERSION, get_worker_contract,
    validate_worker_input, validate_worker_output,
)


class WorkerContractTests(unittest.TestCase):
    def test_every_supported_workflow_node_has_versioned_contract(self):
        node_types = (
            "market_input", "data_quality", "sma", "ema", "rsi", "macd",
            "bollinger", "returns", "volatility", "research_summary",
        )
        for node_type in node_types:
            contract = get_worker_contract(node_type)
            self.assertEqual(contract["contract_version"], CONTRACT_VERSION)
            self.assertEqual(contract["node_type"], node_type)
            self.assertIn("evidence_requirements", contract)

    def test_contract_is_defensive_copy(self):
        contract = get_worker_contract("sma")
        contract["output"]["required_keys"].append("corrupted")
        self.assertNotIn("corrupted", get_worker_contract("sma")["output"]["required_keys"])

    def test_input_shape_validation(self):
        validate_worker_input("sma", [1, 2, 3])
        validate_worker_input("sma", {"values": [1, 2, 3]})
        with self.assertRaises(ValueError):
            validate_worker_input("sma", "not-a-series")
        validate_worker_input("market_input", None)

    def test_output_required_keys_validation(self):
        validate_worker_output("sma", {"series": [1.0], "period": 2})
        with self.assertRaises(ValueError):
            validate_worker_output("sma", {"series": [1.0]})
        validate_worker_output("volatility", 0.25)

    def test_unknown_node_contract_rejected(self):
        with self.assertRaises(ValueError):
            get_worker_contract("unknown")


if __name__ == "__main__":
    unittest.main()
