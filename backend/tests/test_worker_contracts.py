import unittest

from app.worker_contracts import (
    CONTRACT_VERSION, get_worker_contract,
    validate_worker_input, validate_worker_output, validate_evidence_provenance,
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

    def test_numeric_series_contract_rejects_booleans_strings_and_non_finite_values(self):
        for payload in ([1, True, 3], [1, "2", 3], [1, float("inf")], [1, 10 ** 1000]):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    validate_worker_input("sma", payload)

    def test_object_contract_requires_a_numeric_series_field(self):
        validate_worker_input("sma", {"close": [1, 2.5, 3]})
        validate_worker_input("sma", {"data": {"values": [1, 2, 3]}})
        with self.assertRaisesRegex(ValueError, "must contain"):
            validate_worker_input("sma", {"metadata": "not observations"})
        with self.assertRaisesRegex(ValueError, "must be a list"):
            validate_worker_input("sma", {"values": "1,2,3"})

    def test_output_required_keys_validation(self):
        validate_worker_output("sma", {"series": [1.0], "period": 2})
        with self.assertRaises(ValueError):
            validate_worker_output("sma", {"series": [1.0]})
        validate_worker_output("volatility", 0.25)

    def test_output_contract_rejects_non_finite_nested_numbers(self):
        for output in (
            {"series": [1.0, float("nan")], "period": 2},
            {"series": [1.0, float("inf")], "period": 2},
            {"series": [1.0, 10 ** 1000], "period": 2},
            {"macd": [1.0], "signal": [float("-inf")], "histogram": [0.0]},
        ):
            node_type = "macd" if "macd" in output else "sma"
            with self.subTest(node_type=node_type, output=output):
                with self.assertRaisesRegex(ValueError, "finite numbers"):
                    validate_worker_output(node_type, output)

    def test_evidence_provenance_requires_source_timestamp_and_quality(self):
        validate_evidence_provenance({
            "input_source": "provider:sample",
            "retrieval_timestamp": "2026-11-10T12:30:00Z",
            "quality_status": "pass",
        })
        for evidence in (
            {},
            {"input_source": "provider"},
            {"input_source": "provider", "retrieval_timestamp": "not-a-date",
             "quality_status": "pass"},
            {"input_source": "provider", "retrieval_timestamp": "2026-11-10T12:30:00",
             "quality_status": "pass"},
            {"input_source": " ", "retrieval_timestamp": "2026-11-10T12:30:00Z",
             "quality_status": "pass"},
            {"input_source": "provider", "retrieval_timestamp": "2026-11-10T12:30:00Z",
             "quality_status": "unsupported"},
        ):
            with self.subTest(evidence=evidence):
                with self.assertRaises(ValueError):
                    validate_evidence_provenance(evidence)

    def test_unknown_node_contract_rejected(self):
        with self.assertRaises(ValueError):
            get_worker_contract("unknown")


if __name__ == "__main__":
    unittest.main()
