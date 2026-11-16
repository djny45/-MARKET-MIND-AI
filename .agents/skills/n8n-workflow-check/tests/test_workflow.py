import copy
import importlib.util
import json
import math
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("checker", SKILL / "scripts" / "check_workflow.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class WorkflowCheckTests(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads((SKILL / "assets" / "validated-events.json").read_text())

    def test_fixture_is_structurally_valid(self):
        self.assertEqual(checker.check(self.workflow), [])

    def test_missing_target_is_rejected(self):
        self.workflow["connections"]["Sample events"]["main"][0][0]["node"] = "Missing"
        self.assertIn("Connection points at an unknown node.", checker.check(self.workflow))

    def test_duplicate_identity_is_rejected(self):
        self.workflow["nodes"][1]["id"] = self.workflow["nodes"][0]["id"]
        self.assertIn("Duplicate node id.", checker.check(self.workflow))

    def test_active_workflow_is_rejected(self):
        self.workflow["active"] = True
        self.assertIn("Shareable workflow must explicitly set active=false.", checker.check(self.workflow))

    def test_malformed_edge_does_not_crash(self):
        self.workflow["connections"]["Sample events"]["main"] = [None]
        self.assertIn("Connection output must be an array.", checker.check(self.workflow))

    def test_malformed_targets_are_rejected(self):
        for target in ([], {}, None, True, 1):
            with self.subTest(target=target):
                self.workflow["connections"]["Sample events"]["main"][0][0]["node"] = target
                self.assertIn("Connection points at an unknown node.", checker.check(self.workflow))

    def test_nonfinite_type_version_is_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                self.workflow["nodes"][0]["typeVersion"] = value
                self.assertIn("Node 0 needs a finite positive typeVersion.", checker.check(self.workflow))

    def test_credentials_are_rejected(self):
        self.workflow["nodes"][1]["credentials"] = {"x": {"id": "private-binding"}}
        self.assertTrue(checker.check(self.workflow))

    def test_secret_values_are_not_echoed(self):
        secret = "private-fixture-value"
        self.workflow["nodes"][1]["parameters"]["password"] = secret
        errors = checker.check(self.workflow)
        self.assertTrue(errors)
        self.assertNotIn(secret, str(errors))

    def test_checker_does_not_mutate_input(self):
        original = copy.deepcopy(self.workflow)
        checker.check(self.workflow)
        self.assertEqual(self.workflow, original)


if __name__ == "__main__":
    unittest.main()
