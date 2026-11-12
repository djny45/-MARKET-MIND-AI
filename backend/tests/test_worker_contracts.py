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

    def test_specialist_inputs_enforce_minimum_observation_counts(self):
        validate_worker_input("returns", [10, 11])
        validate_worker_input("volatility", [10, 11, 12])
        for node_type, payload in (
            ("returns", [10]),
            ("volatility", [10, 11]),
            ("volatility", {"values": [10]}),
        ):
            with self.subTest(node_type=node_type, payload=payload):
                with self.assertRaisesRegex(ValueError, "at least"):
                    validate_worker_input(node_type, payload)

    def test_volatility_object_output_requires_typed_statistics(self):
        validate_worker_output("volatility", {
            "per_observation": 0.12, "observations": 8, "annualized": 1.9,
        })
        for output in (
            {},
            {"per_observation": 0.12},
            {"per_observation": "0.12", "observations": 8},
            {"per_observation": 0.12, "observations": True},
        ):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    validate_worker_output("volatility", output)

    def test_rsi_contract_enforces_typed_period_and_series(self):
        validate_worker_output("rsi", {"series": [None, 45.0], "period": 2})
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validate_worker_output("rsi", {"series": [45.0], "period": 0})

    def test_output_required_keys_validation(self):
        validate_worker_output("sma", {"series": [1.0], "period": 2})
        with self.assertRaises(ValueError):
            validate_worker_output("sma", {"series": [1.0]})
        validate_worker_output("volatility", 0.25)

    def test_declared_typed_fields_are_enforced(self):
        validate_worker_output("data_quality", {"data": {"values": [1, 2]}, "quality": {"status": "pass"}})
        validate_worker_output("returns", {"series": [0.1, 0.2], "summary": {"mean": 0.15}})
        validate_worker_output("research_summary", {"report": {"findings": []}})
        invalid = (
            ("data_quality", {"data": [], "quality": {}}),
            ("returns", {"series": [0.1], "summary": []}),
            ("research_summary", {"report": "not-an-object"}),
            ("bollinger", {"middle": [1.0], "upper": [2.0], "lower": [0.0], "period": True}),
        )
        for node_type, output in invalid:
            with self.subTest(node_type=node_type, output=output):
                with self.assertRaises(ValueError):
                    validate_worker_output(node_type, output)

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

    def test_market_input_output_requires_finite_numeric_values(self):
        from app.worker_contracts import validate_worker_output
        for values in (["12"], [True], [float("inf")], None):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    validate_worker_output("market_input", {"values": values})

    def test_output_contract_rejects_non_numeric_analytical_series(self):
        invalid_outputs = (
            ("sma", {"series": [1.0, "bad"], "period": 2}),
            ("ema", {"series": [1.0, None], "period": 2}),
            ("macd", {"macd": [1.0], "signal": [True], "histogram": [0.0]}),
            ("bollinger", {"middle": [1.0], "upper": ["2.0"], "lower": [0.0]}),
        )
        for node_type, output in invalid_outputs:
            with self.subTest(node_type=node_type, output=output):
                with self.assertRaisesRegex(ValueError, r"must be a number"):
                    validate_worker_output(node_type, output)

    def test_rsi_output_allows_only_leading_warmup_nulls(self):
        validate_worker_output("rsi", {"series": [None, None, 48.5, 52.0], "period": 3})
        validate_worker_output("rsi", {"series": [None, None], "period": 14})
        for series in ([48.5, None, 52.0], [None, "bad", 52.0], [None, True, 52.0]):
            with self.subTest(series=series):
                with self.assertRaises(ValueError):
                    validate_worker_output("rsi", {"series": series, "period": 3})

    def test_period_output_must_be_a_positive_integer(self):
        for period in (0, -1, 2.5, True, "14"):
            with self.subTest(period=period):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    validate_worker_output("sma", {"series": [1.0], "period": period})

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
