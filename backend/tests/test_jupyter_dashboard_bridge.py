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

    def test_published_page_ships_both_renderers_exactly_once(self):
        """The page needs both renderers, because the two routes have opposite rules.

        Verified in a real browser (Camofox, 2026-11-25):
          * the loopback proxy sends `script-src 'self'`, so it refuses inline JS
            and renders only through the external `market_mind_dashboard.js`;
          * Jupyter's `/files/` sends `sandbox allow-scripts`, which gives the
            document an opaque origin and refuses the external same-URL script,
            so it renders only through the injected inline copy.
        Removing either copy leaves one route blank. Duplicating it wastes bytes
        and is how template drift previously went unnoticed, so assert exactly
        one of each and that the inline copy matches the external source.
        """
        snap = bridge.build_snapshot(FakeClient())
        html, renderer = self._published_html(snap)

        inline = re.findall(r"<script>(.*?)</script>", html, re.S)
        self.assertEqual(len(inline), 1, "exactly one inline renderer must be injected")
        self.assertIn(inline[0].strip(), renderer,
                      "injected renderer must come from market_mind_dashboard.js")

        external = re.findall(r'<script src="market_mind_dashboard\.js\?v=[^"]+"></script>', html)
        self.assertEqual(len(external), 1, "exactly one external renderer must be referenced")
        self.assertIn('id="mm-snapshot"', html)

    def test_publish_is_idempotent_across_cycles(self):
        """Republishing must not accumulate inline renderers (the race guard).

        The bridge runs every 20s for the life of the session. If a concurrent
        edit adds a second copy of the renderer to the template, or a stale
        publisher appends one on top of an already-rendered page, the page grows
        on every cycle. Publishing twice from the same input must be byte-stable.
        """
        snap = bridge.build_snapshot(FakeClient())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "market_mind_live.html"
            bridge.PUBLISH = [out]
            bridge.PUBLISH_DIRS = []
            bridge.STATE = Path(tmp) / "state.json"
            # Freeze the timestamp so two cycles produce identical snapshots.
            snap = dict(snap, generated_at="2026-11-25T00:00:00Z")
            bridge.publish(snap)
            first = out.read_text(encoding="utf-8")
            bridge.publish(snap)
            second = out.read_text(encoding="utf-8")
        self.assertEqual(first, second, "repeated publish must not duplicate the renderer")
        self.assertEqual(len(re.findall(r"<script>", second)), 1)

    def test_snapshot_is_embedded_as_parseable_json(self):
        snap = bridge.build_snapshot(FakeClient())
        html, _ = self._published_html(snap)
        match = re.search(r'id="mm-snapshot">(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        embedded = json.loads(match.group(1))
        self.assertEqual(embedded["pnl"]["registered_agents"], 550)
        self.assertIs(embedded["broker_execution"], False)

    def test_template_source_never_inlines_executable_script(self):
        """Guard the source file, not just the published output.

        A concurrent editor previously pasted the renderer into the template,
        which silently broke the proxy route (its `script-src 'self'` refuses
        inline JS). Catching it in the template makes the failure immediate and
        independent of whatever the publisher does at render time.
        """
        raw = bridge.TEMPLATE.read_text(encoding="utf-8")
        inline = re.findall(
            r"<script(?![^>]*type=\"application/json\")(?![^>]*\bsrc=)[^>]*>", raw)
        self.assertEqual(inline, [], "template must not contain inline executable script")
        self.assertIn('id="mm-snapshot"', raw)
        self.assertIn('src="market_mind_dashboard.js?v=__MM_VERSION__"', raw)
        self.assertTrue(bridge.DASHBOARD_JS.is_file(),
                        "external renderer must exist next to the template")
        self.assertNotIn("MARKET-MIND-AI private dashboard renderer", raw,
                         "renderer must not be duplicated into the template")

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
