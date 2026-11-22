import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CamofoxBrowserConfigTests(unittest.TestCase):
    def _assert_no_secret_env(self, env: dict | None) -> None:
        env = env or {}
        for key in ("CAMOFOX_API_KEY", "CAMOFOX_ACCESS_KEY", "CAMOFOX_ADMIN_KEY"):
            self.assertNotIn(key, env)
        self.assertEqual(env.get("CAMOFOX_BASE_URL"), "http://127.0.0.1:9377")

    def test_portable_mcp_config_registers_camofox_separately(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertIn("market-mind-ai", config)
        self.assertIn("camofox-browser", config)
        entry = config["camofox-browser"]
        self.assertEqual(entry["command"], "npx")
        self.assertIn("@askjo/camofox-browser-mcp", entry["args"])
        self._assert_no_secret_env(entry.get("env"))

    def test_cursor_and_codex_configs_match(self):
        cursor = json.loads((ROOT / ".cursor/mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertIn("camofox-browser", cursor)
        self._assert_no_secret_env(cursor["camofox-browser"].get("env"))

        codex = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
        servers = codex["mcp_servers"]
        self.assertIn("market_mind_ai", servers)
        self.assertIn("camofox-browser", servers)
        self._assert_no_secret_env(servers["camofox-browser"].get("env"))

    def test_read_only_server_does_not_import_camofox(self):
        source = (ROOT / "backend/app/mcp_server.py").read_text(encoding="utf-8")
        self.assertNotIn("camofox", source.lower())

    def test_security_design_and_setup_script_exist(self):
        doc = (ROOT / "docs/CAMOFOX-BROWSER-SECURITY.md").read_text(encoding="utf-8")
        for phrase in ("127.0.0.1", "CAMOFOX_API_KEY", "no agent may", "untrusted"):
            self.assertIn(phrase.lower(), doc.lower())
        script = (ROOT / "scripts/setup_camofox_browser.sh").read_text(encoding="utf-8")
        self.assertIn("CAMOFOX_BIND_HOST=127.0.0.1", script)
        self.assertIn("unset CAMOFOX_API_KEY", script)
        self.assertIn("node24", script)
        self.assertIn('"$NODE_MAJOR" -lt 24', script)
        self.assertIn("LD_LIBRARY_PATH", script)

    def test_agent_instructions_state_browser_boundary(self):
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("camofox-browser", instructions)
        self.assertIn("brokerage orders", instructions)
        self.assertIn("untrusted data", instructions)


if __name__ == "__main__":
    unittest.main()
