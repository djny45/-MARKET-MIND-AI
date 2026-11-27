#!/usr/bin/env python3
"""Check that supported coding-agent instruction adapters stay present."""
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "AGENTS.md": ("MARKET-MIND-AI agent instructions", "The local MCP server is"),
    ".github/copilot-instructions.md": ("AGENTS.md",),
    ".cursor/rules/market-mind.mdc": ("alwaysApply: true", "AGENTS.md", ".cursor/mcp.json"),
    ".agents/skills/n8n-workflow-check/SKILL.md": ("name: n8n-workflow-check",),
    "docs/AI-HARNESS-COMPATIBILITY.md": ("Claude Code", "Codex", "GitHub Copilot", "Cursor", "backend/app/mcp_server.py"),
    ".mcp.json": ("mcpServers", "backend/app/mcp_server.py"),
    ".cursor/mcp.json": ("mcpServers", "backend/app/mcp_server.py"),
    ".codex/config.toml": ("[mcp_servers.market_mind_ai]", "backend/app/mcp_server.py"),
    "backend/app/mcp_server.py": ("market_mind_capabilities", "mcp_server_diagnostics", "validate_n8n_workflow_json", "workflow_activation"),
    "backend/tests/test_mcp_server.py": ("MarketMindMCPTests", "test_mcp_lists_only_read_only_tools", "test_all_four_harness_configs_launch_the_same_stdio_tools"),
}
errors = []
for relative, markers in REQUIRED.items():
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"Missing adapter file: {relative}")
        continue
    content = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in content:
            errors.append(f"{relative}: required marker missing: {marker}")
if errors:
    raise SystemExit("\n".join(errors))
# Parse the native client configurations and verify they launch the same stdio server.
try:
    expected_args = ["backend/app/mcp_server.py"]
    for relative in (".mcp.json", ".cursor/mcp.json"):
        config = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        entry = config["mcpServers"]["market-mind-ai"]
        expected_cwd = "." if relative == ".cursor/mcp.json" else None
        if (
            entry.get("command") not in {"python", "python3", "py"}
            or entry.get("args") != expected_args
            or entry.get("cwd") != expected_cwd
        ):
            errors.append(f"{relative}: unexpected MCP server launch command.")

    codex = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    entry = codex["mcp_servers"]["market_mind_ai"]
    if entry.get("command") not in {"python", "python3", "py"} or entry.get("args") != expected_args:
        errors.append(".codex/config.toml: unexpected MCP server launch command.")
except (OSError, ValueError, KeyError, TypeError) as exc:
    errors.append(f"Invalid native MCP client configuration: {type(exc).__name__}")

if errors:
    raise SystemExit("\n".join(errors))
print(f"Harness adapter check passed: {len(REQUIRED)} files and 3 MCP configs")
