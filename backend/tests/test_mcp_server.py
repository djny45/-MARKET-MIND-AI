import json
import sys
import tomllib
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
                "mcp_server_diagnostics",
                "list_engineering_skills",
                "read_engineering_skill",
                "validate_n8n_workflow_json",
                "browser_research_read",
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
        self.assertEqual(len(names), 6)

    async def test_all_four_harness_configs_launch_the_same_stdio_tools(self):
        root = Path(__file__).resolve().parents[2]
        root_config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
        cursor_config = json.loads((root / ".cursor/mcp.json").read_text(encoding="utf-8"))
        codex_config = tomllib.loads((root / ".codex/config.toml").read_text(encoding="utf-8"))

        # Claude Code and GitHub Copilot both consume the workspace-root
        # portable .mcp.json; Cursor and Codex use their native project files.
        harness_entries = {
            "claude-code": root_config["mcpServers"]["market-mind-ai"],
            "github-copilot": root_config["mcpServers"]["market-mind-ai"],
            "cursor": cursor_config["mcpServers"]["market-mind-ai"],
            "codex": codex_config["mcp_servers"]["market_mind_ai"],
        }
        for harness, entry in harness_entries.items():
            with self.subTest(harness=harness):
                command = entry["command"]
                args = entry["args"]
                self.assertIn(command, {"python", "python3", "py"})
                self.assertEqual(args, ["backend/app/mcp_server.py"])
                server = StdioServerParameters(
                    command=sys.executable,
                    args=[str(root / args[0])],
                    cwd=str(root),
                )
                async with Client(stdio_client(server), raise_exceptions=True) as client:
                    response = await client.list_tools()
                self.assertEqual(
                    {tool.name for tool in response.tools},
                    {
                        "market_mind_capabilities",
                        "mcp_server_diagnostics",
                        "list_engineering_skills",
                        "read_engineering_skill",
                        "validate_n8n_workflow_json",
                        "browser_research_read",
                    },
                )

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

    async def test_mcp_diagnostics_are_sanitized_and_confirm_safety_boundaries(self):
        async with Client(mcp, raise_exceptions=True) as client:
            response = await client.call_tool("mcp_server_diagnostics", {})
        data = response.structured_content
        self.assertEqual(data["server"], "market-mind-ai")
        self.assertEqual(data["transport"], "stdio")
        self.assertTrue(data["python_version"])
        self.assertTrue(data["mcp_sdk_version"])
        self.assertFalse(data["secret_values_exposed"])
        self.assertEqual(data["external_network_access"], "read_only_allowlisted_https")
        self.assertFalse(data["browser_research"]["javascript"])
        self.assertFalse(data["browser_research"]["downloads"])
        self.assertFalse(data["repository_write_access"])
        self.assertFalse(data["workflow_import"])
        self.assertFalse(data["workflow_activation"])
        self.assertFalse(data["workflow_execution"])
        self.assertFalse(data["brokerage_execution"])

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
