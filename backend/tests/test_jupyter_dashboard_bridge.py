"""Tests for the Jupyter dashboard bridge (no network, no credentials)."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / "scripts"))

import jupyter_dashboard_bridge as bridge  # noqa: E402


class FakeClient:
    """Returns deterministic API payloads; no login or real requests."""

    def __init__(self, status=None, portfolios=None, overview=None):
        self.payloads = {
            "/api/paper/status": (200, status or {
                "registered_agents": 550, "agents_with_open_positions": 2,
                "total_virtual_capital": 275000.0, "total_portfolio_value": 275000.0,
            }),
            "/api/paper/portfolios": (200, portfolios or {"portfolios": [
                {"agent_id": "agent_0001", "realized_pnl": 10.0, "max_drawdown": 0.01,
                 "positions": [{"symbol": "AAPL", "quantity": 2}]},
            ]}),
            "/api/market-data/overview": (200, overview or {"bars": []}),
        }
        self.bars = (overview or {}).get("bars", [])

    def request(self, method, path, body=None):
        if path.startswith("/api/paper/trades?"):
            return (200, {"trades": [
                {"agent_id": "agent_0001", "symbol": "AAPL", "side": "BUY",
                 "quantity": 1, "price": 100.0, "pnl": 0, "executed_at": "2026-01-01T00:00:00Z"}
            ]})
        if path.startswith("/api/market-data/history?"):
            # The bridge asks per-symbol; only replay bars for the requested symbol.
            symbol = path.split("symbol=", 1)[1].split("&", 1)[0] if "symbol=" in path else ""
            return (200, {"bars": [b for b in self.bars if b.get("symbol") == symbol]})
        return self.payloads[path]


class BridgeTests(unittest.TestCase):
    def test_snapshot_uses_backend_values(self):
        snap = bridge.build_snapshot(FakeClient())
        self.assertEqual(snap["pnl"]["registered_agents"], 550)
        self.assertEqual(snap["pnl"]["total_virtual_capital"], 275000.0)
        self.assertEqual(snap["pnl"]["realized_pnl"], 10.0)
        self.assertEqual(snap["broker_execution"], False)
        self.assertEqual(len(snap["open_positions"]), 1)

    def test_no_live_prices_without_feed(self):
        snap = bridge.build_snapshot(FakeClient())
        self.assertEqual(snap["market_data_status"], "unavailable")
        self.assertEqual(snap["market_prices"], [])

    def test_prices_published_only_with_real_observations(self):
        # The bridge queries these symbols specifically, so the fixture must use one.
        bars = [{"symbol": "BTCUSD", "close": 101.5, "source": "stored", "status": "ok",
                 "timestamp": "2026-01-01T00:00:00Z"}]
        snap = bridge.build_snapshot(FakeClient(overview={"bars": bars}))
        self.assertEqual(snap["market_data_status"], "available")
        self.assertEqual(snap["market_prices"][0]["symbol"], "BTCUSD")

    def _published_html(self, snap):
        """Run the real publish() into a temp dir and return the page and JS."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "market_mind_live.html"
            bridge.PUBLISH = [out]
            bridge.PUBLISH_DIRS = []
            bridge.STATE = Path(tmp) / "state.json"
            bridge.publish(snap)
            return out.read_text(encoding="utf-8"), bridge.DASHBOARD_JS.read_text(encoding="utf-8")

    def test_published_page_has_no_inline_executable_script(self):
        """The private proxy sends `script-src 'self'`, which refuses inline JS.

        A regression here is invisible in a plain browser check and only shows up
        as a blank dashboard behind the proxy, so it is asserted directly.
        """
        snap = bridge.build_snapshot(FakeClient())
        html, _ = self._published_html(snap)
        inline = re.findall(r"<script(?![^>]*type=\"application/json\")(?![^>]*\bsrc=)[^>]*>", html)
        self.assertEqual(inline, [], "dashboard must not rely on inline executable script")
        self.assertIn('id="mm-snapshot"', html)
        self.assertIn("market_mind_dashboard.js?v=", html)

    def test_snapshot_is_embedded_as_parseable_json(self):
        snap = bridge.build_snapshot(FakeClient())
        html, _ = self._published_html(snap)
        match = re.search(r'id="mm-snapshot">(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        embedded = json.loads(match.group(1))
        self.assertEqual(embedded["pnl"]["registered_agents"], 550)
        self.assertIs(embedded["broker_execution"], False)

    def test_template_placeholders_are_valid_json_before_substitution(self):
        """A stale publisher must not be able to corrupt the data block."""
        raw = bridge.TEMPLATE.read_text(encoding="utf-8")
        match = re.search(r'id="mm-snapshot">(.*?)</script>', raw, re.S)
        self.assertIsNotNone(match)
        self.assertIsInstance(json.loads(match.group(1)), str)

    def test_snapshot_payload_cannot_break_out_of_data_block(self):
        snap = bridge.build_snapshot(FakeClient())
        snap["paper_note"] = "</script><img src=x onerror=alert(1)>"
        html, _ = self._published_html(snap)
        self.assertNotIn("</script><img", html)
        match = re.search(r'id="mm-snapshot">(.*?)</script>', html, re.S)
        self.assertEqual(json.loads(match.group(1))["paper_note"], snap["paper_note"])


if __name__ == "__main__":
    unittest.main()
