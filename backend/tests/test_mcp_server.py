import json
import sys
import unittest
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp_server import mcp


class MarketMindMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_lists_only_read_only_tools(self):
        async with Client(mcp, raise_exceptions=True) as client:
            response = await client.list_tools()
        names = {tool.name for tool in response.tools}
        self.assertEqual(
            names,
            {
                "market_mind_capabilities",
                "list_engineering_skills",
                "read_engineering_skill",
                "validate_n8n_workflow_json",
            },
        )
        self.assertFalse(any("import" in name or "execute" in name for name in names))

    async def test_stdio_subprocess_discovers_tools_like_a_coding_harness(self):
        server_script = Path(__file__).resolve().parents[1] / "app" / "mcp_server.py"
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(server_script)],
        )
        async with Client(stdio_client(server), raise_exceptions=True) as client:
            response = await client.list_tools()
        names = {tool.name for tool in response.tools}
        self.assertIn("market_mind_capabilities", names)
        self.assertIn("validate_n8n_workflow_json", names)
        self.assertEqual(len(names), 4)

    async def test_capabilities_declare_research_only_boundaries(self):
        async with Client(mcp, raise_exceptions=True) as client:
            response = await client.call_tool("market_mind_capabilities", {})
        data = response.structured_content
        self.assertEqual(data["name"], "MARKET-MIND-AI")
        self.assertTrue(data["coding_harness_independent"])
        self.assertFalse(data["brokerage_execution"])
        self.assertFalse(data["workflow_activation"])
        self.assertFalse(data["workflow_execution"])
        self.assertFalse(data["workflow_import"])

    async def test_engineering_skill_allowlist_and_read(self):
        async with Client(mcp, raise_exceptions=True) as client:
            listed = await client.call_tool("list_engineering_skills", {})
            read = await client.call_tool(
                "read_engineering_skill",
                {"skill_id": "rea-tool-design"},
            )
            denied = await client.call_tool(
                "read_engineering_skill",
                {"skill_id": "../../README.md"},
            )
        data = listed.structured_content
        self.assertEqual(data["count"], 4)
        self.assertFalse(data["trading_skill_content_exposed"])

        skill = read.structured_content
        self.assertEqual(skill["id"], "rea-tool-design")
        self.assertIn("tool", skill["content"].lower())
        self.assertFalse(skill["side_effects"])
        self.assertEqual(denied.structured_content["error"], "skill_not_allowlisted")

    async def test_n8n_validator_accepts_structural_fixture_without_runtime_claim(self):
        workflow = {
            "name": "MCP validation fixture",
            "active": False,
            "nodes": [
                {
                    "id": "manual-1",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "parameters": {},
                }
            ],
            "connections": {},
        }
        async with Client(mcp, raise_exceptions=True) as client:
            response = await client.call_tool(
                "validate_n8n_workflow_json",
                {"workflow_json": json.dumps(workflow)},
            )
        result = response.structured_content
        self.assertTrue(result["structurally_valid"])
        self.assertFalse(result["runtime_verified"])

    async def test_n8n_validator_rejects_nonstandard_json_and_oversized_payloads(self):
        async with Client(mcp, raise_exceptions=True) as client:
            nonstandard = await client.call_tool(
                "validate_n8n_workflow_json",
                {"workflow_json": '{"active": false, "nodes": [], "connections": {}, "x": NaN}'},
            )
            oversized = await client.call_tool(
                "validate_n8n_workflow_json",
                {"workflow_json": "x" * 1_000_001},
            )
        self.assertFalse(nonstandard.structured_content["structurally_valid"])
        self.assertIn("not valid JSON", nonstandard.structured_content["errors"][0])
        self.assertFalse(oversized.structured_content["structurally_valid"])
        self.assertIn("character limit", oversized.structured_content["errors"][0])

    async def test_n8n_validator_rejects_active_or_invalid_json(self):
        active = {
            "name": "Active workflow",
            "active": True,
            "nodes": [
                {
                    "id": "manual-1",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "parameters": {},
                }
            ],
            "connections": {},
        }
        async with Client(mcp, raise_exceptions=True) as client:
            response = await client.call_tool(
                "validate_n8n_workflow_json",
                {"workflow_json": json.dumps(active)},
            )
            invalid = await client.call_tool(
                "validate_n8n_workflow_json",
                {"workflow_json": "{not-json"},
            )
        self.assertFalse(response.structured_content["structurally_valid"])
        self.assertFalse(response.structured_content["runtime_verified"])
        self.assertFalse(invalid.structured_content["structurally_valid"])
        self.assertIn("not valid JSON", invalid.structured_content["errors"][0])


if __name__ == "__main__":
    unittest.main()
