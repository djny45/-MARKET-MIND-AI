import unittest

from app.n8n_workflow_validation import validate_n8n_workflow


def valid_workflow():
    return {
        "name": "Research intake example",
        "active": False,
        "nodes": [
            {"id": "node-1", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "parameters": {}},
            {"id": "node-2", "name": "Set Result", "type": "n8n-nodes-base.set", "typeVersion": 3, "parameters": {}},
        ],
        "connections": {
            "Manual Trigger": {
                "main": [[{"node": "Set Result", "type": "main", "index": 0}]]
            }
        },
    }


class N8NWorkflowValidationTests(unittest.TestCase):
    def test_valid_inactive_export_passes_structural_check(self):
        result = validate_n8n_workflow(valid_workflow())
        self.assertTrue(result["structurally_valid"])
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["runtime_verified"])

    def test_active_workflow_is_rejected(self):
        workflow = valid_workflow()
        workflow["active"] = True
        self.assertIn("active=false", " ".join(validate_n8n_workflow(workflow)["errors"]))

    def test_duplicate_node_ids_and_names_are_rejected(self):
        workflow = valid_workflow()
        workflow["nodes"][1]["id"] = "node-1"
        workflow["nodes"][1]["name"] = "Manual Trigger"
        errors = validate_n8n_workflow(workflow)["errors"]
        self.assertIn("Duplicate node id.", errors)
        self.assertIn("Duplicate node name.", errors)

    def test_dangling_connection_is_rejected(self):
        workflow = valid_workflow()
        workflow["connections"]["Manual Trigger"]["main"][0][0]["node"] = "Missing"
        self.assertIn("Connection points at an unknown node.", validate_n8n_workflow(workflow)["errors"])

    def test_credentials_are_rejected_without_echoing_values(self):
        workflow = valid_workflow()
        workflow["nodes"][0]["credentials"] = {"httpBasicAuth": {"id": "secret-id"}}
        result = validate_n8n_workflow(workflow)
        self.assertFalse(result["structurally_valid"])
        self.assertNotIn("secret-id", str(result["errors"]))

    def test_embedded_secret_is_flagged_without_echoing_value(self):
        workflow = valid_workflow()
        workflow["nodes"][0]["parameters"] = {"password": "not-for-logs"}
        result = validate_n8n_workflow(workflow)
        self.assertFalse(result["structurally_valid"])
        self.assertNotIn("not-for-logs", str(result["errors"]))

    def test_malformed_node_version_is_rejected(self):
        workflow = valid_workflow()
        workflow["nodes"][0]["typeVersion"] = float("nan")
        self.assertIn("finite positive typeVersion", " ".join(validate_n8n_workflow(workflow)["errors"]))

    def test_non_object_input_is_rejected(self):
        result = validate_n8n_workflow([])
        self.assertFalse(result["structurally_valid"])
        self.assertFalse(result["runtime_verified"])


if __name__ == "__main__":
    unittest.main()
