#!/usr/bin/env python3
"""Check that supported coding-agent instruction adapters stay present."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "AGENTS.md": ("MARKET-MIND-AI agent instructions", "The local MCP server is"),
    "CLAUDE.md": ("@AGENTS.md",),
    ".github/copilot-instructions.md": ("AGENTS.md",),
    ".cursor/rules/market-mind.mdc": ("alwaysApply: true", "AGENTS.md", ".cursor/mcp.json"),
    ".agents/skills/n8n-workflow-check/SKILL.md": ("name: n8n-workflow-check",),
    ".claude/skills/n8n-workflow-check/SKILL.md": ("name: n8n-workflow-check", ".agents/skills/n8n-workflow-check/SKILL.md"),
    "docs/AI-HARNESS-COMPATIBILITY.md": ("Claude Code", "Codex", "GitHub Copilot", "Cursor", "backend/app/mcp_server.py"),
    ".mcp.json": ("mcpServers", "backend/app/mcp_server.py"),
    ".cursor/mcp.json": ("mcpServers", "backend/app/mcp_server.py"),
    ".codex/config.toml": ("[mcp_servers.market_mind_ai]", "backend/app/mcp_server.py"),
    "backend/app/mcp_server.py": ("market_mind_capabilities", "validate_n8n_workflow_json", "workflow_activation"),
    "backend/tests/test_mcp_server.py": ("MarketMindMCPTests", "test_mcp_lists_only_read_only_tools"),
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
print(f"Harness adapter check passed: {len(REQUIRED)} files")
